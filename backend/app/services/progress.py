"""Save check results. The server compares strings; it does not run learner code."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.practice import PracticeEvent
from app.models.progress import ExerciseProgress, UserStats
from app.models.track import Track, UserTrackAccess
from app.models.user import User
from app.services.check_engine import check_attempt
from app.services.content_store import ContentError
from app.services.tracks import list_visible_tracks

# DECISION: each revealed hint costs 2 XP, and a finished exercise is not paid again.
HINT_XP_COST = 2


def _touch_streak(stats: UserStats, today: date) -> None:
    previous = stats.last_active_date
    if previous == today:
        return
    if previous == today - timedelta(days=1):
        stats.current_streak_days += 1
    else:
        stats.current_streak_days = 1
    stats.longest_streak_days = max(stats.longest_streak_days, stats.current_streak_days)
    stats.last_active_date = today


async def _stats_for(session: AsyncSession, user_id: uuid.UUID) -> UserStats:
    stats = await session.scalar(select(UserStats).where(UserStats.user_id == user_id))
    if stats is None:
        stats = UserStats(user_id=user_id, xp=0, current_streak_days=0, longest_streak_days=0)
        session.add(stats)
        await session.flush()
    return stats


async def _load_exercise(session: AsyncSession, exercise_id: uuid.UUID) -> Exercise:
    row = await session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.lesson).selectinload(Lesson.module).selectinload(Module.track)
        )
    )
    if row is None:
        raise ContentError(404, "Exercise not found")
    return row


def _visible(exercise: Exercise) -> bool:
    lesson = exercise.lesson
    return (
        exercise.status == "published"
        and lesson.status == "published"
        and lesson.module.status == "published"
        and lesson.module.track.is_active
    )


async def submit_check(
    session: AsyncSession,
    user: User,
    exercise_id: uuid.UUID,
    *,
    attempt: str,
    output: str | None,
    hints_used: int,
    wpm: int | None,
    accuracy: int | None,
    duration_seconds: int | None = None,
) -> dict:
    exercise = await _load_exercise(session, exercise_id)
    from app.security.roles import is_staff

    if not is_staff(user.role) and not _visible(exercise):
        raise ContentError(404, "Exercise not found")
    if not is_staff(user.role):
        access = await session.scalar(
            select(UserTrackAccess.id).where(
                UserTrackAccess.user_id == user.id,
                UserTrackAccess.track_id == exercise.lesson.module.track_id,
            )
        )
        if access is None:
            raise ContentError(403, "You do not have access to this track")
    outcome = check_attempt(exercise.data or {}, attempt, output)
    progress = await session.scalar(
        select(ExerciseProgress).where(
            ExerciseProgress.user_id == user.id,
            ExerciseProgress.exercise_id == exercise.id,
        )
    )
    if progress is None:
        progress = ExerciseProgress(
            user_id=user.id,
            exercise_id=exercise.id,
            status="started",
            attempts=0,
            hints_used=0,
        )
        session.add(progress)
        await session.flush()
    already = progress.status == "completed"
    progress.attempts += 1
    progress.hints_used = max(progress.hints_used, hints_used)
    if wpm is not None:
        progress.best_wpm = wpm if progress.best_wpm is None else max(progress.best_wpm, wpm)
    if accuracy is not None:
        progress.best_accuracy = (
            accuracy if progress.best_accuracy is None else max(progress.best_accuracy, accuracy)
        )
    awarded = 0
    if outcome.passed and not already:
        base = int((exercise.data or {}).get("xp") or 0)
        awarded = max(0, base - progress.hints_used * HINT_XP_COST)
        progress.status = "completed"
        progress.completed_at = datetime.now(UTC)
    stats = await _stats_for(session, user.id)
    stats.xp += awarded
    _touch_streak(stats, datetime.now(UTC).date())
    if outcome.passed:
        session.add(
            PracticeEvent(
                user_id=user.id,
                exercise_id=exercise.id,
                source="lesson",
                passed=True,
                wpm=wpm,
                accuracy=accuracy,
                duration_seconds=duration_seconds,
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
        "status": progress.status,
    }


async def progress_for_exercises(
    session: AsyncSession, user_id: uuid.UUID, exercise_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    if not exercise_ids:
        return {}
    rows = list(
        (
            await session.scalars(
                select(ExerciseProgress).where(
                    ExerciseProgress.user_id == user_id,
                    ExerciseProgress.exercise_id.in_(exercise_ids),
                )
            )
        ).all()
    )
    return {
        row.exercise_id: {
            "status": row.status,
            "attempts": row.attempts,
            "hints_used": row.hints_used,
            "best_wpm": row.best_wpm,
            "best_accuracy": row.best_accuracy,
        }
        for row in rows
    }


async def dashboard(session: AsyncSession, user: User) -> dict:
    tracks = await list_visible_tracks(session, user)
    track_ids = [track.id for track in tracks]
    stats = await session.scalar(select(UserStats).where(UserStats.user_id == user.id))
    if not track_ids:
        return _dashboard_body(stats, [])
    rows = list(
        (
            await session.execute(
                select(
                    Track.id,
                    Lesson.id,
                    Lesson.title,
                    Exercise.id,
                )
                .join(Module, Module.track_id == Track.id)
                .join(Lesson, Lesson.module_id == Module.id)
                .join(Exercise, Exercise.lesson_id == Lesson.id)
                .where(
                    Track.id.in_(track_ids),
                    Module.status == "published",
                    Lesson.status == "published",
                    Exercise.status == "published",
                )
                .order_by(Track.position, Module.position, Lesson.position, Exercise.position)
            )
        ).all()
    )
    completed = set(
        (
            await session.scalars(
                select(ExerciseProgress.exercise_id).where(
                    ExerciseProgress.user_id == user.id,
                    ExerciseProgress.status == "completed",
                )
            )
        ).all()
    )
    grouped: dict[uuid.UUID, dict] = {
        track.id: {
            "slug": track.slug,
            "name": track.name,
            "description": track.description,
            "icon": track.icon,
            "color": track.color,
            "order": track.position,
            "completed": 0,
            "total": 0,
            "continue_lesson_id": None,
            "continue_lesson_title": None,
        }
        for track in tracks
    }
    for track_id, lesson_id, lesson_title, exercise_id in rows:
        item = grouped[track_id]
        item["total"] += 1
        if exercise_id in completed:
            item["completed"] += 1
        elif item["continue_lesson_id"] is None:
            item["continue_lesson_id"] = lesson_id
            item["continue_lesson_title"] = lesson_title
    return _dashboard_body(stats, [grouped[track.id] for track in tracks])


def _dashboard_body(stats: UserStats | None, tracks: list[dict]) -> dict:
    return {
        "xp": 0 if stats is None else stats.xp,
        "current_streak_days": 0 if stats is None else stats.current_streak_days,
        "longest_streak_days": 0 if stats is None else stats.longest_streak_days,
        "tracks": tracks,
    }


async def lesson_states(
    session: AsyncSession, user_id: uuid.UUID, lesson_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Map each lesson to new, started, or done."""
    if not lesson_ids:
        return {}
    rows = list(
        (
            await session.execute(
                select(Exercise.lesson_id, Exercise.id, ExerciseProgress.status)
                .join(
                    ExerciseProgress,
                    (ExerciseProgress.exercise_id == Exercise.id)
                    & (ExerciseProgress.user_id == user_id),
                    isouter=True,
                )
                .where(Exercise.lesson_id.in_(lesson_ids), Exercise.status == "published")
            )
        ).all()
    )
    buckets: dict[uuid.UUID, list[str | None]] = {lesson_id: [] for lesson_id in lesson_ids}
    for lesson_id, _exercise_id, status in rows:
        buckets.setdefault(lesson_id, []).append(status)
    result = {}
    for lesson_id, statuses in buckets.items():
        if statuses and all(item == "completed" for item in statuses):
            result[lesson_id] = "done"
        elif any(item for item in statuses):
            result[lesson_id] = "started"
        else:
            result[lesson_id] = "new"
    return result


async def _exercise_ids_for_lessons(
    session: AsyncSession, lesson_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    if not lesson_ids:
        return []
    return list(
        (
            await session.scalars(
                select(Exercise.id).where(Exercise.lesson_id.in_(lesson_ids))
            )
        ).all()
    )


async def _published_modules_for_track(session: AsyncSession, track_id: uuid.UUID) -> list[Module]:
    return list(
        (
            await session.scalars(
                select(Module)
                .where(Module.track_id == track_id, Module.status == "published")
                .options(selectinload(Module.lessons))
                .order_by(Module.position)
            )
        ).all()
    )


async def _require_visible_track(session: AsyncSession, user: User, slug: str) -> Track:
    tracks = await list_visible_tracks(session, user)
    track = next((item for item in tracks if item.slug == slug), None)
    if track is None:
        raise ContentError(404, "Track not found")
    return track


async def _resolve_reset_exercise_ids(
    session: AsyncSession,
    user: User,
    *,
    scope: str,
    track_slug: str | None,
    level: str | None,
    module_id: uuid.UUID | None,
    lesson_id: uuid.UUID | None,
) -> tuple[list[uuid.UUID], str]:
    """Return exercise ids to clear and a short label for the UI notice."""
    from app.services.content_store import _assign_module_levels

    if scope == "all":
        ids = list(
            (
                await session.scalars(
                    select(ExerciseProgress.exercise_id).where(ExerciseProgress.user_id == user.id)
                )
            ).all()
        )
        return ids, "all languages"

    if scope == "track":
        track = await _require_visible_track(session, user, track_slug or "")
        modules = await _published_modules_for_track(session, track.id)
        lesson_ids = [
            lesson.id
            for module in modules
            for lesson in module.lessons
            if lesson.status == "published"
        ]
        return await _exercise_ids_for_lessons(session, lesson_ids), track.name

    if scope == "level":
        track = await _require_visible_track(session, user, track_slug or "")
        modules = await _published_modules_for_track(session, track.id)
        leveled = _assign_module_levels(modules)
        band = level or "beginner"
        lesson_ids = [
            lesson["id"]
            for module in leveled
            if module.get("level") == band
            for lesson in module["lessons"]
        ]
        label = {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}.get(
            band, band
        )
        return await _exercise_ids_for_lessons(session, lesson_ids), f"{track.name} · {label}"

    if scope == "module":
        if module_id is None:
            raise ContentError(400, "module_id is required")
        module = await session.scalar(
            select(Module)
            .where(Module.id == module_id)
            .options(selectinload(Module.track), selectinload(Module.lessons))
        )
        if module is None:
            raise ContentError(404, "Module not found")
        await _require_visible_track(session, user, module.track.slug)
        lesson_ids = [lesson.id for lesson in module.lessons if lesson.status == "published"]
        return await _exercise_ids_for_lessons(session, lesson_ids), module.title

    if lesson_id is None:
        raise ContentError(400, "lesson_id is required")
    lesson = await session.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(selectinload(Lesson.module).selectinload(Module.track))
    )
    if lesson is None:
        raise ContentError(404, "Lesson not found")
    await _require_visible_track(session, user, lesson.module.track.slug)
    return await _exercise_ids_for_lessons(session, [lesson.id]), lesson.title


async def _recompute_xp(session: AsyncSession, user_id: uuid.UUID) -> int:
    rows = list(
        (
            await session.execute(
                select(ExerciseProgress.hints_used, Exercise.data).join(
                    Exercise, Exercise.id == ExerciseProgress.exercise_id
                ).where(
                    ExerciseProgress.user_id == user_id,
                    ExerciseProgress.status == "completed",
                )
            )
        ).all()
    )
    total = 0
    for hints_used, data in rows:
        base = int((data or {}).get("xp") or 0)
        total += max(0, base - int(hints_used or 0) * HINT_XP_COST)
    stats = await _stats_for(session, user_id)
    stats.xp = total
    return total


async def reset_progress(
    session: AsyncSession,
    user: User,
    *,
    scope: str,
    track_slug: str | None = None,
    level: str | None = None,
    module_id: uuid.UUID | None = None,
    lesson_id: uuid.UUID | None = None,
) -> dict:
    """Delete exercise progress for a learning-path slice and recompute XP."""
    exercise_ids, label = await _resolve_reset_exercise_ids(
        session,
        user,
        scope=scope,
        track_slug=track_slug,
        level=level,
        module_id=module_id,
        lesson_id=lesson_id,
    )
    cleared = 0
    if exercise_ids:
        rows = list(
            (
                await session.scalars(
                    select(ExerciseProgress).where(
                        ExerciseProgress.user_id == user.id,
                        ExerciseProgress.exercise_id.in_(exercise_ids),
                    )
                )
            ).all()
        )
        cleared = len(rows)
        for row in rows:
            await session.delete(row)
    xp_total = await _recompute_xp(session, user.id)
    await session.commit()
    return {
        "cleared": cleared,
        "scope": scope,
        "label": label,
        "xp_total": xp_total,
    }
