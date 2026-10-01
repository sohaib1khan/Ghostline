"""Games draw published exercises from tracks the learner can open."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.practice import PracticeEvent
from app.models.progress import UserStats
from app.models.user import User
from app.services.check_engine import check_attempt
from app.services.content_store import ContentError
from app.services.progress import _stats_for, _touch_streak
from app.services.tracks import list_visible_tracks

# DECISION: a game pays 5 XP the first time this learner passes that exercise
# in that game. Lesson XP stays on POST /api/check, so games do not finish a lesson.
GAME_XP = 5
GAMES = ("speed_drill", "bug_hunt", "command_roulette", "fill_frenzy")
LEADERBOARD_KEY = "leaderboard_enabled"
# Soft default session length. The UI may offer longer runs; the pool size is the ceiling.
DEFAULT_SESSION_ROUNDS = 10


def break_code(code: str) -> str:
    chars = list(code)
    for index in range(len(chars) - 1, -1, -1):
        if chars[index].isalnum():
            chars[index] = "y" if chars[index] == "x" else "x"
            return "".join(chars)
    return f"{code} "


def _code_text():
    return func.coalesce(Exercise.data["code"].as_string(), "")


def _prompt_text():
    return func.coalesce(Exercise.data["prompt"].as_string(), "")


def _suitable(game: str, exercise: Exercise) -> bool:
    data = exercise.data or {}
    code = str(data.get("code") or "")
    prompt = str(data.get("prompt") or "").strip()
    if game == "speed_drill":
        return exercise.type == "trace" and bool(code.strip())
    if game == "bug_hunt":
        # DECISION: only full-line traces. Fill prompts + a flipped letter (Dune→Dunx)
        # make learners copy the bug while hints talk about a blank.
        return (
            exercise.type == "trace"
            and bool(code.strip())
            and break_code(code) != code
        )
    if game == "fill_frenzy":
        return exercise.type == "fill" and bool(data.get("blanks"))
    if game == "command_roulette":
        # Recall/challenge only — fill prompts expect a blank UI, not a free type.
        return exercise.type in {"recall", "challenge"} and bool(prompt)
    return False


def _sql_filters(game: str) -> list:
    """Narrow in SQL so the whole published catalog is eligible, not a random 40."""
    code = _code_text()
    if game == "speed_drill":
        return [Exercise.type == "trace", code != ""]
    if game == "bug_hunt":
        # break_code() still runs in Python; every non-empty line flips or grows.
        return [Exercise.type == "trace", code != ""]
    if game == "fill_frenzy":
        blanks = Exercise.data["blanks"]
        return [
            Exercise.type == "fill",
            func.jsonb_typeof(blanks) == "array",
            func.jsonb_array_length(blanks) > 0,
        ]
    if game == "command_roulette":
        return [Exercise.type.in_(("recall", "challenge")), _prompt_text() != ""]
    return [False]


def _bug_hints(code: str, broken: str) -> list[str]:
    hints = [
        "One character was flipped. Find it, then type the corrected line.",
        "Do not copy the red line as-is — fix the typo first.",
    ]
    # Point at the first differing index without giving the whole answer away early.
    for index, (left, right) in enumerate(zip(code, broken, strict=False)):
        if left != right:
            start = max(0, index - 2)
            end = min(len(code), index + 3)
            snippet = code[start:end]
            hints.append(f"Look near `{snippet}` in the correct line.")
            break
    if len(code) <= 80:
        hints.append(f"The correct line is `{code}`.")
    return hints[:8]


def _public_round(game: str, exercise: Exercise, *, pool_size: int) -> dict:
    from app.services.content_store import _practice_hints

    data = exercise.data or {}
    code = str(data.get("code") or "")
    body = {
        "game": game,
        "exercise_id": exercise.id,
        "prompt": data.get("prompt") or "",
        "track_slug": exercise.lesson.module.track.slug,
        "lesson_title": exercise.lesson.title,
        "type": exercise.type,
        "hints": _practice_hints(exercise.type, data),
        "pool_size": pool_size,
        "session_rounds": min(DEFAULT_SESSION_ROUNDS, max(pool_size, 1)),
    }
    if game == "speed_drill":
        body["code"] = code
        body["tokens"] = data.get("tokens") or []
    elif game == "bug_hunt":
        broken = break_code(code)
        body["broken"] = broken
        body["tokens"] = data.get("tokens") or []
        body["prompt"] = "One character is wrong. Type the corrected line."
        body["hints"] = _bug_hints(code, broken)
    elif game == "fill_frenzy":
        body["code"] = code
        body["blanks"] = data.get("blanks") or []
    else:
        limit = data.get("time_limit_seconds") or 45
        body["time_limit_seconds"] = int(limit)
        # Guided recall: show a worked snippet after the first miss / via hint path.
        if code:
            body["example"] = code
            body["tokens"] = data.get("tokens") or []
    return body


def _published_base(track_ids: list):
    return and_(
        Exercise.status == "published",
        Lesson.status == "published",
        Module.status == "published",
        Module.track_id.in_(track_ids),
    )


def _pool_query(track_ids: list, game: str, exclude: uuid.UUID | None):
    filters = [_published_base(track_ids), *_sql_filters(game)]
    if exclude is not None:
        filters.append(Exercise.id != exclude)
    return (
        select(Exercise)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(*filters)
        .options(
            selectinload(Exercise.lesson).selectinload(Lesson.module).selectinload(Module.track)
        )
    )


async def count_pool(session: AsyncSession, game: str, track_ids: list) -> int:
    if not track_ids:
        return 0
    stmt = (
        select(func.count())
        .select_from(Exercise)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(_published_base(track_ids), *_sql_filters(game))
    )
    return int(await session.scalar(stmt) or 0)


async def catalog(session: AsyncSession, user: User) -> dict:
    tracks = await list_visible_tracks(session, user)
    from app.services.settings_store import get_setting

    stored = await get_setting(session, LEADERBOARD_KEY)
    enabled = isinstance(stored, dict) and bool(stored.get("enabled"))
    track_payload = []
    for track in tracks:
        pools = {}
        for game in GAMES:
            pools[game] = await count_pool(session, game, [track.id])
        track_payload.append(
            {
                "slug": track.slug,
                "name": track.name,
                "pools": pools,
                "published_exercises": sum(pools.values()),
            }
        )
    return {
        "tracks": track_payload,
        "default_session_rounds": DEFAULT_SESSION_ROUNDS,
        "games": [
            {
                "id": "speed_drill",
                "name": "Speed Drill",
                "blurb": "Trace published snippets from your lessons until the keys feel automatic.",
                "needs": "trace",
            },
            {
                "id": "bug_hunt",
                "name": "Bug Hunt",
                "blurb": "One character is wrong on a typed line from your lessons. Fix it — do not copy the typo.",
                "needs": "code",
            },
            {
                "id": "command_roulette",
                "name": "Command Roulette",
                "blurb": "Timed recall and challenge prompts from your published lessons. Hints stay with you.",
                "needs": "prompt",
            },
            {
                "id": "fill_frenzy",
                "name": "Fill Frenzy",
                "blurb": "Only fill exercises — type into the blank, not the whole line.",
                "needs": "fill",
            },
        ],
        "leaderboard_enabled": enabled,
    }


async def next_round(
    session: AsyncSession,
    user: User,
    game: str,
    track_slug: str | None,
    exclude: uuid.UUID | None,
) -> dict:
    if game not in GAMES:
        raise ContentError(400, "Unknown game")
    tracks = await list_visible_tracks(session, user)
    if track_slug:
        tracks = [track for track in tracks if track.slug == track_slug]
        if not tracks:
            raise ContentError(403, "You do not have access to this track")
    elif game == "command_roulette":
        # No track chosen: prefer Bash when available, else any visible track.
        bash = [track for track in tracks if track.slug == "bash"]
        tracks = bash or tracks
    if not tracks:
        raise ContentError(404, "No exercises for that game yet")
    track_ids = [track.id for track in tracks]
    pool_size = await count_pool(session, game, track_ids)
    if pool_size == 0:
        raise ContentError(
            404,
            "No published exercises fit this game yet. Publish lessons on the track, or pick another game.",
        )
    stmt = _pool_query(track_ids, game, exclude)
    # ORDER BY random() over the filtered set so every imported published exercise can appear.
    rows = list((await session.scalars(stmt.order_by(func.random()).limit(120))).all())
    suitable = [row for row in rows if _suitable(game, row)]
    if not suitable:
        all_rows = list((await session.scalars(_pool_query(track_ids, game, exclude))).all())
        suitable = [row for row in all_rows if _suitable(game, row)]
        if not suitable and exclude is not None:
            # Last resort: allow a repeat when the pool is tiny.
            all_rows = list((await session.scalars(_pool_query(track_ids, game, None))).all())
            suitable = [row for row in all_rows if _suitable(game, row)]
    chosen = suitable[0] if suitable else None
    if chosen is None:
        raise ContentError(404, "No published exercises fit this game yet.")
    return _public_round(game, chosen, pool_size=pool_size)


async def score_round(
    session: AsyncSession,
    user: User,
    game: str,
    exercise_id: uuid.UUID,
    *,
    attempt: str,
    output: str | None,
    wpm: int | None,
    accuracy: int | None,
    hints_used: int = 0,
    duration_seconds: int | None = None,
) -> dict:
    if game not in GAMES:
        raise ContentError(400, "Unknown game")
    exercise = await session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.lesson).selectinload(Lesson.module).selectinload(Module.track)
        )
    )
    if exercise is None or exercise.status != "published":
        raise ContentError(404, "Exercise not found")
    lesson = exercise.lesson
    track = lesson.module.track
    visible = (
        lesson.status == "published" and lesson.module.status == "published" and track.is_active
    )
    if not visible or not _suitable(game, exercise):
        raise ContentError(404, "Exercise not found")
    allowed = await list_visible_tracks(session, user)
    if track.id not in {item.id for item in allowed}:
        raise ContentError(403, "You do not have access to this track")
    outcome = check_attempt(exercise.data or {}, attempt, output)
    awarded = 0
    if outcome.passed:
        prior = await session.scalar(
            select(PracticeEvent.id).where(
                PracticeEvent.user_id == user.id,
                PracticeEvent.exercise_id == exercise.id,
                PracticeEvent.source == game,
                PracticeEvent.passed.is_(True),
                PracticeEvent.xp_awarded > 0,
            )
        )
        if prior is None:
            # Soft penalty for hints so guided play still pays, just a little less.
            awarded = max(1, GAME_XP - min(hints_used, 2))
    stats = await _stats_for(session, user.id)
    stats.xp += awarded
    _touch_streak(stats, datetime.now(UTC).date())
    session.add(
        PracticeEvent(
            user_id=user.id,
            exercise_id=exercise.id,
            source=game,
            passed=outcome.passed,
            wpm=wpm if outcome.passed else None,
            accuracy=accuracy if outcome.passed else None,
            duration_seconds=duration_seconds if outcome.passed else None,
            xp_awarded=awarded,
        )
    )
    await session.commit()
    return {
        "passed": outcome.passed,
        "failed_rule_hint": outcome.hint,
        "failed_kind": outcome.failed_kind,
        "xp_awarded": awarded,
        "xp_total": stats.xp,
        "hints_used": hints_used,
    }


async def leaderboard(session: AsyncSession) -> list[dict]:
    from app.services.settings_store import get_setting

    stored = await get_setting(session, LEADERBOARD_KEY)
    if not (isinstance(stored, dict) and stored.get("enabled")):
        raise ContentError(404, "The leaderboard is off")
    rows = list(
        (
            await session.execute(
                select(User.first_name, UserStats.xp, UserStats.current_streak_days)
                .join(UserStats, UserStats.user_id == User.id)
                .where(User.status == "approved", UserStats.xp > 0)
                .order_by(UserStats.xp.desc(), User.first_name)
                .limit(10)
            )
        ).all()
    )
    return [
        {"name": row.first_name, "xp": row.xp, "streak_days": row.current_streak_days}
        for row in rows
    ]
