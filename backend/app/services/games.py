"""Games draw published exercises from tracks the learner can open."""

from __future__ import annotations

import random
import re
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
from app.services.game_guides import (
    crossword_tokens,
    guide_for,
    hangman_tokens,
    merge_hints,
    progressive_token_hints,
    starter_hints,
)
from app.services.progress import _stats_for, _touch_streak
from app.services.tracks import list_visible_tracks

# DECISION: a game pays 5 XP the first time this learner passes that exercise
# in that game. Lesson XP stays on POST /api/check, so games do not finish a lesson.
GAME_XP = 5
LEADERBOARD_KEY = "leaderboard_enabled"
DEFAULT_SESSION_ROUNDS = 10

# Keep PracticeEvent.source check constraint in sync (migration 0009).
GAME_DEFS: list[dict] = [
    {
        "id": "speed_drill",
        "name": "Speed Drill",
        "blurb": "Trace published snippets until the keys feel automatic.",
        "needs": "trace",
        "category": "classic",
    },
    {
        "id": "ghost_race",
        "name": "Ghost Race",
        "blurb": "Race a faded replay of your own best run on the same snippet.",
        "needs": "trace",
        "category": "learn",
    },
    {
        "id": "bug_hunt",
        "name": "Bug Hunt",
        "blurb": "One character is wrong. Find and fix it — do not copy the typo.",
        "needs": "trace",
        "category": "learn",
    },
    {
        "id": "fill_frenzy",
        "name": "Fill Frenzy",
        "blurb": "Only fill exercises — type into the blank, not the whole line.",
        "needs": "fill",
        "category": "classic",
    },
    {
        "id": "command_roulette",
        "name": "Command Roulette",
        "blurb": "Timed recall and challenge prompts from your published lessons.",
        "needs": "prompt",
        "category": "classic",
    },
    {
        "id": "code_hangman",
        "name": "Code Hangman",
        "blurb": "Guess a keyword from its explanation. Wrong letters fade the ghost.",
        "needs": "tokens",
        "category": "classic",
    },
    {
        "id": "codele",
        "name": "Codele",
        "blurb": "Wordle for code — guess a 5-letter keyword with green/yellow feedback.",
        "needs": "tokens",
        "category": "classic",
    },
    {
        "id": "memory_match",
        "name": "Memory Match",
        "blurb": "Flip cards to pair a command with what it does.",
        "needs": "tokens",
        "category": "classic",
    },
    {
        "id": "code_crossword",
        "name": "Code Crossword",
        "blurb": "Clues are token explanations; fill the keywords.",
        "needs": "tokens",
        "category": "classic",
    },
    {
        "id": "tic_tac_toe",
        "name": "Code Tic-Tac-Toe",
        "blurb": "Win a cell by answering a mini-question. Three in a row wins.",
        "needs": "mixed",
        "category": "classic",
    },
    {
        "id": "syntax_snake",
        "name": "Syntax Snake",
        "blurb": "Eat tokens in the right order to rebuild the statement.",
        "needs": "trace",
        "category": "classic",
    },
    {
        "id": "predict_output",
        "name": "Predict the Output",
        "blurb": "Read the snippet and pick what it prints.",
        "needs": "output",
        "category": "learn",
    },
    {
        "id": "code_scramble",
        "name": "Code Scramble",
        "blurb": "Drag shuffled lines back into order (Parsons puzzle).",
        "needs": "trace",
        "category": "learn",
    },
    {
        "id": "query_detective",
        "name": "Query Detective",
        "blurb": "See a result table — write the SQL that produces it.",
        "needs": "sql",
        "category": "learn",
    },
    {
        "id": "boss_battle",
        "name": "Boss Battle",
        "blurb": "A mixed chain of questions. Correct answers damage the boss.",
        "needs": "mixed",
        "category": "learn",
    },
]

GAMES = tuple(item["id"] for item in GAME_DEFS)


def break_code(code: str) -> str:
    """Mutate a correct line with language-agnostic typos for Bug Hunt."""
    mutations = [
        ("===", "=="),
        ("==", "="),
        ("!=", "="),
        (":", ""),
        (";", ""),
        ("-la", "-l"),
        ("WHERE", "HAVING"),
        ("where", "having"),
        ("range(1, 4)", "range(1, 3)"),
        ("range(1,4)", "range(1,3)"),
        ("append", "extend"),
        ("SELECT", "SELCT"),
        ("const ", "let "),
        ("defer ", "defr "),
    ]
    for old, new in mutations:
        if old in code and old != new:
            return code.replace(old, new, 1)
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


def _output_text():
    return func.coalesce(Exercise.data["simulated_output"].as_string(), "")


def _tokens(data: dict) -> list[dict]:
    rows = data.get("tokens") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        match = str(row.get("match") or "").strip()
        explain = str(row.get("explain") or "").strip()
        if match and explain:
            out.append({"match": match, "explain": explain})
    return out


def _five_letter_tokens(data: dict) -> list[dict]:
    return [
        row
        for row in _tokens(data)
        if len(re.sub(r"[^A-Za-z]", "", row["match"])) == 5
    ]


def _word_key(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", token).upper()


def _split_code_tokens(code: str) -> list[str]:
    parts = [part for part in re.split(r"(\s+|[(),.;=+\-*/<>!]+)", code.strip()) if part.strip()]
    return parts[:16]


def _suitable(game: str, exercise: Exercise) -> bool:
    data = exercise.data or {}
    code = str(data.get("code") or "")
    prompt = str(data.get("prompt") or "").strip()
    tokens = _tokens(data)
    output = str(data.get("simulated_output") or "").strip()
    if game in {"speed_drill", "ghost_race"}:
        return exercise.type == "trace" and bool(code.strip())
    if game == "bug_hunt":
        return (
            exercise.type == "trace"
            and bool(code.strip())
            and break_code(code) != code
        )
    if game == "fill_frenzy":
        return exercise.type == "fill" and bool(data.get("blanks"))
    if game == "command_roulette":
        return exercise.type in {"recall", "challenge"} and bool(prompt)
    if game in {"code_hangman", "code_crossword"}:
        return len(hangman_tokens(tokens) if game == "code_hangman" else crossword_tokens(tokens)) >= 1
    if game == "memory_match":
        return len(tokens) >= 1
    if game == "codele":
        return len(_five_letter_tokens(data)) >= 1
    if game == "predict_output":
        return bool(code.strip()) and bool(output)
    if game == "code_scramble":
        lines = [line for line in code.splitlines() if line.strip()]
        return exercise.type == "trace" and len(lines) >= 2
    if game == "syntax_snake":
        return exercise.type == "trace" and len(_split_code_tokens(code)) >= 3
    if game == "query_detective":
        slug = ""
        try:
            slug = exercise.lesson.module.track.slug if exercise.lesson else ""
        except Exception:
            slug = ""
        return bool(output) and (
            exercise.type in {"trace", "fill", "challenge"}
            or "select" in code.lower()
            or slug == "sql"
        )
    if game in {"tic_tac_toe", "boss_battle"}:
        return (
            (exercise.type == "fill" and bool(data.get("blanks")))
            or (exercise.type in {"recall", "challenge"} and bool(prompt))
            or (exercise.type == "trace" and bool(code.strip()) and bool(output))
            or len(tokens) >= 1
        )
    return False


def _sql_filters(game: str) -> list:
    code = _code_text()
    tokens = Exercise.data["tokens"]
    output = _output_text()
    if game in {"speed_drill", "ghost_race"}:
        return [Exercise.type == "trace", code != ""]
    if game == "bug_hunt":
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
    if game in {"code_hangman", "memory_match", "code_crossword", "codele"}:
        return [
            func.jsonb_typeof(tokens) == "array",
            func.jsonb_array_length(tokens) > 0,
        ]
    if game == "predict_output":
        return [code != "", output != ""]
    if game == "code_scramble":
        return [Exercise.type == "trace", code != ""]
    if game == "syntax_snake":
        return [Exercise.type == "trace", code != ""]
    if game == "query_detective":
        return [output != ""]
    if game in {"tic_tac_toe", "boss_battle"}:
        return []  # broad; filtered in Python
    return [False]


def _bug_hints(code: str, broken: str) -> list[str]:
    hints = [
        "One detail was mutated. Find it, then type the corrected line.",
        "Do not copy the red line as-is — fix the bug first.",
    ]
    for index, (left, right) in enumerate(zip(code, broken, strict=False)):
        if left != right:
            start = max(0, index - 2)
            end = min(len(code), index + 3)
            hints.append(f"Look near `{code[start:end]}` in the correct line.")
            break
    if len(code) <= 80:
        hints.append(f"The correct line is `{code}`.")
    return hints[:8]


def _stable_index(exercise_id: uuid.UUID, size: int) -> int:
    if size <= 0:
        return 0
    return exercise_id.int % size


def _pick_token(data: dict, exercise_id: uuid.UUID, *, five_letter: bool = False, hangman: bool = False) -> dict | None:
    if five_letter:
        rows = _five_letter_tokens(data)
    elif hangman:
        rows = hangman_tokens(_tokens(data))
    else:
        rows = _tokens(data)
    if not rows:
        return None
    return rows[_stable_index(exercise_id, len(rows))]


def _track_slug(exercise: Exercise) -> str:
    try:
        return exercise.lesson.module.track.slug
    except Exception:
        return ""


def _with_guide(body: dict, game: str, track_slug: str) -> dict:
    body["guide"] = guide_for(game, track_slug)
    return body


def _base_hints(game: str, track_slug: str, exercise_type: str, data: dict) -> list[str]:
    from app.services.content_store import _practice_hints

    return merge_hints(starter_hints(game, track_slug), _practice_hints(exercise_type, data), limit=10)


async def _distractor_outputs(
    session: AsyncSession, track_ids: list, correct: str, limit: int = 3
) -> list[str]:
    stmt = (
        select(Exercise.data)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(
            _published_base(track_ids),
            _output_text() != "",
            _output_text() != correct,
        )
        .order_by(func.random())
        .limit(24)
    )
    rows = list(await session.scalars(stmt))
    options: list[str] = []
    for data in rows:
        text = str((data or {}).get("simulated_output") or "").strip()
        if text and text not in options and text != correct:
            options.append(text)
        if len(options) >= limit:
            break
    while len(options) < limit:
        options.append(f"(other output {len(options) + 1})")
    return options


def _public_round(game: str, exercise: Exercise, *, pool_size: int, extra: dict | None = None) -> dict:
    data = exercise.data or {}
    code = str(data.get("code") or "")
    track_slug = _track_slug(exercise)
    body = {
        "game": game,
        "exercise_id": exercise.id,
        "prompt": data.get("prompt") or "",
        "track_slug": track_slug,
        "lesson_title": exercise.lesson.title,
        "type": exercise.type,
        "hints": _base_hints(game, track_slug, exercise.type, data),
        "pool_size": pool_size,
        "session_rounds": min(DEFAULT_SESSION_ROUNDS, max(pool_size, 1)),
        "category": next((item["category"] for item in GAME_DEFS if item["id"] == game), "classic"),
    }
    if extra:
        body.update(extra)

    if game in {"speed_drill", "ghost_race"}:
        body["code"] = code
        body["tokens"] = data.get("tokens") or []
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                "Type the faded ghost text from left to right.",
                "A small typo still fails — re-read the line once.",
                f"The line is `{code}`." if len(code) <= 80 else "Match every character of the snippet.",
            ],
            limit=8,
        )
    elif game == "bug_hunt":
        broken = break_code(code)
        body["broken"] = broken
        body["tokens"] = data.get("tokens") or []
        body["prompt"] = "Something is wrong. Type the corrected line."
        body["hints"] = merge_hints(starter_hints(game, track_slug), _bug_hints(code, broken), limit=8)
    elif game == "fill_frenzy":
        body["code"] = code
        body["blanks"] = data.get("blanks") or []
        body["hints"] = _base_hints(game, track_slug, "fill", data)
    elif game == "command_roulette":
        limit = data.get("time_limit_seconds") or 45
        body["time_limit_seconds"] = int(limit)
        if code:
            body["example"] = code
            body["tokens"] = data.get("tokens") or []
        body["hints"] = _base_hints(game, track_slug, exercise.type, data)
    elif game == "code_hangman":
        token = body.pop("_token")
        word = token["match"]
        body["prompt"] = token["explain"]
        body["word_length"] = len(word)
        body["pattern"] = [" " if ch.isspace() else ("_" if ch.isalnum() else ch) for ch in word]
        body["hints"] = progressive_token_hints(
            word=word,
            explain=token.get("explain") or "",
            track_slug=track_slug,
            game=game,
        )
    elif game == "codele":
        token = body.pop("_token")
        word = re.sub(r"[^A-Za-z]", "", token["match"]).upper()[:5]
        body["prompt"] = token["explain"]
        body["word_length"] = 5
        body["max_guesses"] = 6
        body["hints"] = progressive_token_hints(
            word=word,
            explain=token.get("explain") or "",
            track_slug=track_slug,
            game=game,
        )
        body["_secret"] = word
    elif game == "memory_match":
        tokens = _tokens(data)[:6]
        cards = []
        for index, token in enumerate(tokens):
            cards.append({"id": f"m{index}", "pair": index, "text": token["match"], "kind": "match"})
            cards.append(
                {"id": f"e{index}", "pair": index, "text": token["explain"], "kind": "explain"}
            )
        random.shuffle(cards)
        body["prompt"] = "Flip two cards. Match each keyword with what it does."
        body["cards"] = cards
        body["pair_count"] = len(tokens)
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                "Start with a keyword card, then hunt its explanation.",
                f"There are {len(tokens)} pairs in this round.",
                "Matched pairs stay face-up.",
            ],
            limit=8,
        )
    elif game == "code_crossword":
        tokens = sorted(crossword_tokens(_tokens(data)), key=lambda row: len(row["match"]), reverse=True)[:8]
        body["prompt"] = "Fill each clue with the matching keyword from your lessons."
        body["clues"] = [
            {
                "id": index,
                "clue": token["explain"],
                "length": len(token["match"]),
                "pattern": "_" * len(token["match"]),
            }
            for index, token in enumerate(tokens)
        ]
        body["_answers"] = [token["match"] for token in tokens]
        first = tokens[0] if tokens else None
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            progressive_token_hints(
                word=first["match"],
                explain=first["explain"],
                track_slug=track_slug,
                game=game,
            )
            if first
            else [],
            limit=8,
        )
    elif game == "predict_output":
        body["code"] = code
        body["prompt"] = "What does this print or return?"
        choices = body.pop("_choices")
        body["choices"] = choices
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                "Read every line before picking.",
                "Eliminate choices that cannot match the types or format.",
                f"One accepted output is `{str(data.get('simulated_output') or '').strip()}`."
                if str(data.get("simulated_output") or "").strip()
                else "Match the exact printed result.",
            ],
            limit=8,
        )
    elif game == "code_scramble":
        usable = [line for line in code.splitlines() if line.strip()]
        shuffled = usable[:]
        random.shuffle(shuffled)
        if shuffled == usable and len(usable) > 1:
            shuffled = usable[1:] + usable[:1]
        body["prompt"] = "Put the lines back in order."
        body["lines"] = [{"id": index, "text": text} for index, text in enumerate(shuffled)]
        body["_ordered"] = usable
        body["indent_matters"] = track_slug in {"python", "go", "csharp", "java"}
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                "Start with the header or first keyword line.",
                "Keep each line’s indentation — spaces travel with the line.",
                f"First line should be `{usable[0]}`." if usable else "Restore top-to-bottom order.",
                "Full order:\n" + "\n".join(usable) if usable else "Restore the original order.",
            ],
            limit=8,
        )
    elif game == "syntax_snake":
        parts = _split_code_tokens(code)
        decoys = ["WHERE", "FROM", "SELECT", "const", "defer", "append", "chmod", "null"]
        options = parts[:]
        for decoy in decoys:
            if decoy not in options:
                options.append(decoy)
            if len(options) >= len(parts) + 4:
                break
        random.shuffle(options)
        body["prompt"] = "Eat tokens in the correct order to rebuild the statement."
        body["target_len"] = len(parts)
        body["options"] = options
        body["_ordered"] = parts
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                f"The statement has {len(parts)} tokens.",
                f"It starts with `{parts[0]}`." if parts else "Follow left-to-right order.",
                f"Next after the first is `{parts[1]}`." if len(parts) > 1 else "Stay in order.",
                "Full path: " + " → ".join(parts) if parts else "Rebuild the line.",
            ],
            limit=8,
        )
    elif game == "query_detective":
        body["prompt"] = "Write a query that produces this result."
        body["result"] = str(data.get("simulated_output") or "")
        body["code"] = ""
        if data.get("blanks"):
            body["blanks"] = data.get("blanks")
            body["scaffold"] = code
        answers = [str(item) for item in ((data.get("check") or {}).get("accepted_answers") or []) if str(item).strip()]
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            [
                "Read the column headers and sample values first.",
                "Name the table and filters that could produce those rows.",
                f"It may start like `{answers[0][:24]}…`" if answers and len(answers[0]) > 24 else (
                    f"One accepted query is `{answers[0]}`." if answers else "Use SELECT … FROM … patterns from your lessons."
                ),
                f"One accepted query is `{answers[0]}`." if answers else "Match the lesson’s accepted SQL.",
            ],
            limit=8,
        )
    elif game == "tic_tac_toe":
        body["prompt"] = "Answer to claim a cell. Wrong answers go to the computer."
        body["cell"] = body.pop("_cell")
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            _base_hints(game, track_slug, exercise.type, data),
            limit=8,
        )
    elif game == "boss_battle":
        body["prompt"] = body.get("prompt") or "Boss battle — answer to deal damage."
        body["boss_hp"] = 8
        body["mode"] = body.pop("_mode")
        if body["mode"] == "trace":
            body["code"] = code
            body["tokens"] = data.get("tokens") or []
        elif body["mode"] == "fill":
            body["code"] = code
            body["blanks"] = data.get("blanks") or []
        elif body["mode"] == "output":
            body["code"] = code
            body["choices"] = body.pop("_choices")
        else:
            if code:
                body["example"] = code
                body["tokens"] = data.get("tokens") or []
        body["hints"] = merge_hints(
            starter_hints(game, track_slug),
            _base_hints(game, track_slug, exercise.type, data),
            [
                "Hints cost your HP in this mode — save them for tough rounds.",
                "A clean answer with no hints deals full damage (bonus XP).",
            ],
            limit=10,
        )

    body.pop("_secret", None)
    body.pop("_answers", None)
    body.pop("_ordered", None)
    body.pop("_token", None)
    return _with_guide(body, game, track_slug)


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
    stmt = _pool_query(track_ids, game, None)
    rows = list(await session.scalars(stmt.limit(200)))
    return sum(1 for row in rows if _suitable(game, row))


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
                **item,
                "guides": {
                    slug: guide_for(item["id"], slug)
                    for slug in ("bash", "python", "go", "javascript", "sql", "csharp", "java")
                },
            }
            for item in GAME_DEFS
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
    elif game in {"command_roulette", "query_detective"}:
        preferred = "sql" if game == "query_detective" else "bash"
        hit = [track for track in tracks if track.slug == preferred]
        tracks = hit or tracks
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
    rows = list((await session.scalars(stmt.order_by(func.random()).limit(120))).all())
    suitable = [row for row in rows if _suitable(game, row)]
    if not suitable:
        all_rows = list((await session.scalars(_pool_query(track_ids, game, exclude))).all())
        suitable = [row for row in all_rows if _suitable(game, row)]
        if not suitable and exclude is not None:
            all_rows = list((await session.scalars(_pool_query(track_ids, game, None))).all())
            suitable = [row for row in all_rows if _suitable(game, row)]
    chosen = suitable[0] if suitable else None
    if chosen is None:
        raise ContentError(404, "No published exercises fit this game yet.")

    data = chosen.data or {}
    extra: dict = {}
    if game == "code_hangman":
        token = _pick_token(data, chosen.id, hangman=True)
        if not token:
            raise ContentError(404, "No tokens for hangman on this exercise.")
        extra["_token"] = token
    elif game == "codele":
        token = _pick_token(data, chosen.id, five_letter=True)
        if not token:
            raise ContentError(404, "No 5-letter tokens for Codele.")
        extra["_token"] = token
    elif game == "predict_output":
        correct = str(data.get("simulated_output") or "").strip()
        distractors = await _distractor_outputs(session, track_ids, correct)
        choices = distractors + [correct]
        random.shuffle(choices)
        extra["_choices"] = choices
        extra["answer_key"] = correct
    elif game == "code_scramble":
        usable = [line for line in str(data.get("code") or "").splitlines() if line.strip()]
        extra["answer_key"] = "\n".join(usable)
    elif game == "syntax_snake":
        parts = _split_code_tokens(str(data.get("code") or ""))
        extra["answer_key"] = " ".join(parts)
    elif game == "memory_match":
        tokens = _tokens(data)[:6]
        extra["answer_key"] = str(len(tokens))
    elif game == "code_crossword":
        tokens = sorted(crossword_tokens(_tokens(data)), key=lambda row: len(row["match"]), reverse=True)[:8]
        extra["answer_key"] = "\n".join(token["match"] for token in tokens)
    elif game == "ghost_race":
        best = await session.scalar(
            select(func.max(PracticeEvent.wpm)).where(
                PracticeEvent.user_id == user.id,
                PracticeEvent.exercise_id == chosen.id,
                PracticeEvent.passed.is_(True),
                PracticeEvent.wpm.is_not(None),
            )
        )
        extra["ghost_wpm"] = int(best) if best else None
    elif game == "tic_tac_toe":
        # Surface as fill/recall/output mini prompt.
        if chosen.type == "fill" and data.get("blanks"):
            extra["_cell"] = {
                "kind": "fill",
                "code": data.get("code") or "",
                "blanks": data.get("blanks") or [],
            }
        elif chosen.type == "trace" and data.get("simulated_output"):
            correct = str(data.get("simulated_output") or "").strip()
            distractors = await _distractor_outputs(session, track_ids, correct)
            choices = distractors[:3] + [correct]
            random.shuffle(choices)
            extra["_cell"] = {
                "kind": "output",
                "code": data.get("code") or "",
                "choices": choices,
            }
            extra["answer_key"] = correct
        else:
            extra["_cell"] = {"kind": "recall", "prompt": data.get("prompt") or ""}
    elif game == "boss_battle":
        if chosen.type == "fill" and data.get("blanks"):
            extra["_mode"] = "fill"
        elif chosen.type == "trace" and data.get("simulated_output"):
            correct = str(data.get("simulated_output") or "").strip()
            distractors = await _distractor_outputs(session, track_ids, correct)
            choices = distractors[:3] + [correct]
            random.shuffle(choices)
            extra["_mode"] = "output"
            extra["_choices"] = choices
            extra["answer_key"] = correct
        elif chosen.type == "trace":
            extra["_mode"] = "trace"
        else:
            extra["_mode"] = "recall"

    public = _public_round(game, chosen, pool_size=pool_size, extra=extra)
    # answer_key must never reach the client.
    public.pop("answer_key", None)
    # Re-attach for games that need server-side compare via a signed approach:
    # we store nothing; score_round re-derives from exercise.
    return public


def _normalize_line(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def _codele_feedback(secret: str, guess: str) -> list[str]:
    secret = secret.upper()
    guess = re.sub(r"[^A-Za-z]", "", guess).upper()[:5].ljust(5)
    result = ["absent"] * 5
    remaining = list(secret)
    for index, ch in enumerate(guess):
        if ch == secret[index]:
            result[index] = "correct"
            remaining[index] = ""
    for index, ch in enumerate(guess):
        if result[index] == "correct":
            continue
        if ch in remaining:
            result[index] = "present"
            remaining[remaining.index(ch)] = ""
    return result


def _reveal_answer(game: str, data: dict, exercise_id: uuid.UUID) -> str:
    """Canonical answer for calm 'see answer' — never returned until the learner asks."""
    code = str(data.get("code") or "").strip()
    answers = [
        str(item).strip()
        for item in ((data.get("check") or {}).get("accepted_answers") or [])
        if str(item).strip()
    ]
    if game in {"speed_drill", "ghost_race", "bug_hunt"}:
        return answers[0] if answers else code
    if game == "fill_frenzy":
        return answers[0] if answers else code
    if game in {"command_roulette", "query_detective", "tic_tac_toe", "boss_battle"}:
        if answers:
            return answers[0]
        output = str(data.get("simulated_output") or "").strip()
        return output or code
    if game == "predict_output":
        return str(data.get("simulated_output") or "").strip()
    if game == "code_scramble":
        usable = [line for line in str(data.get("code") or "").splitlines() if line.strip()]
        return "\n".join(usable)
    if game == "syntax_snake":
        return " ".join(_split_code_tokens(code))
    if game == "code_hangman":
        token = _pick_token(data, exercise_id, hangman=True)
        return (token or {}).get("match") or ""
    if game == "codele":
        token = _pick_token(data, exercise_id, five_letter=True)
        return re.sub(r"[^A-Za-z]", "", (token or {}).get("match", "")).upper()[:5]
    if game == "code_crossword":
        tokens = sorted(crossword_tokens(_tokens(data)), key=lambda row: len(row["match"]), reverse=True)[:8]
        return "\n".join(token["match"] for token in tokens)
    if game == "memory_match":
        tokens = _tokens(data)[:6]
        return "\n".join(f"{token['match']} — {token['explain']}" for token in tokens)
    return answers[0] if answers else code


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
    letters: list[str] | None = None,
    phase: str = "submit",
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

    data = exercise.data or {}
    if phase == "reveal":
        answer = _reveal_answer(game, data, exercise.id)
        return {
            "passed": False,
            "revealed": True,
            "revealed_answer": answer,
            "failed_rule_hint": "Answer shown — try typing it yourself, or skip to the next round.",
            "failed_kind": None,
            "xp_awarded": 0,
            "xp_total": (await _stats_for(session, user.id)).xp,
            "hints_used": hints_used,
        }

    passed = False
    hint = None
    failed_kind = None
    extra: dict = {}

    if game in {
        "speed_drill",
        "ghost_race",
        "bug_hunt",
        "fill_frenzy",
        "command_roulette",
        "query_detective",
        "tic_tac_toe",
        "boss_battle",
    }:
        if game in {"tic_tac_toe", "boss_battle"} and phase == "choice":
            correct = str(data.get("simulated_output") or "").strip()
            passed = attempt.strip() == correct
            if not passed:
                hint = "Not that output — read the snippet again."
                failed_kind = "answers"
        else:
            outcome = check_attempt(data, attempt, output)
            passed = outcome.passed
            hint = outcome.hint
            failed_kind = outcome.failed_kind
    elif game == "code_hangman":
        token = _pick_token(data, exercise.id, hangman=True)
        secret = (token or {}).get("match") or ""
        if phase == "probe":
            guessed = {ch.lower() for ch in (letters or []) if ch}
            mask = [ch if (ch.lower() in guessed or not ch.isalnum()) else "_" for ch in secret]
            wrong = sorted(ch for ch in guessed if ch not in secret.lower())
            extra = {
                "mask": mask,
                "wrong": wrong,
                "lives_left": max(0, 6 - len(wrong)),
                "solved": bool(secret) and "_" not in mask,
            }
            if extra["solved"]:
                attempt = secret
                passed = True
            else:
                return {
                    "passed": False,
                    "failed_rule_hint": None,
                    "failed_kind": None,
                    "xp_awarded": 0,
                    "xp_total": (await _stats_for(session, user.id)).xp,
                    "hints_used": hints_used,
                    **extra,
                }
        else:
            passed = bool(secret) and _word_key(attempt) == _word_key(secret)
            if not passed:
                hint = "Not that keyword — use a hint or try another guess."
                failed_kind = "answers"
    elif game == "codele":
        token = _pick_token(data, exercise.id, five_letter=True)
        secret = re.sub(r"[^A-Za-z]", "", (token or {}).get("match", "")).upper()[:5]
        guess = attempt
        feedback = _codele_feedback(secret, guess)
        extra["feedback"] = feedback
        extra["guess"] = re.sub(r"[^A-Za-z]", "", guess).upper()[:5]
        passed = guess and extra["guess"] == secret
        if not passed:
            hint = "Keep guessing — green is exact, yellow is present."
            failed_kind = "answers"
    elif game == "memory_match":
        # Client sends attempt = number of pairs matched as "done" when complete.
        tokens = _tokens(data)[:6]
        passed = attempt.strip() in {"done", str(len(tokens))} or attempt.strip() == "complete"
        if not passed:
            hint = "Match every pair before finishing."
            failed_kind = "answers"
    elif game == "code_crossword":
        tokens = sorted(crossword_tokens(_tokens(data)), key=lambda row: len(row["match"]), reverse=True)[:8]
        expected = [token["match"] for token in tokens]
        given = [line.strip() for line in attempt.replace("\r\n", "\n").split("\n")]
        passed = len(given) == len(expected) and all(
            _word_key(left) == _word_key(right) for left, right in zip(given, expected, strict=True)
        )
        if not passed:
            hint = "Check each clue length and spelling."
            failed_kind = "answers"
    elif game == "predict_output":
        correct = str(data.get("simulated_output") or "").strip()
        passed = attempt.strip() == correct
        if not passed:
            hint = "Read the code again — another choice is closer."
            failed_kind = "answers"
    elif game == "code_scramble":
        usable = [line for line in str(data.get("code") or "").splitlines() if line.strip()]
        passed = _normalize_line(attempt) == _normalize_line("\n".join(usable))
        if not passed:
            hint = "Watch indentation and line order."
            failed_kind = "answers"
    elif game == "syntax_snake":
        parts = _split_code_tokens(str(data.get("code") or ""))
        got = attempt.split() if " " in attempt else attempt.split("|")
        got = [part for part in got if part]
        passed = got == parts
        if not passed:
            hint = "Follow the statement left to right."
            failed_kind = "answers"
    else:
        outcome = check_attempt(data, attempt, output)
        passed = outcome.passed
        hint = outcome.hint
        failed_kind = outcome.failed_kind

    awarded = 0
    if passed:
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
            awarded = max(1, GAME_XP - min(hints_used, 2))
            if hints_used == 0:
                awarded += 1  # no-hint bonus
    stats = await _stats_for(session, user.id)
    stats.xp += awarded
    _touch_streak(stats, datetime.now(UTC).date())
    session.add(
        PracticeEvent(
            user_id=user.id,
            exercise_id=exercise.id,
            source=game,
            passed=passed,
            wpm=wpm if passed else None,
            accuracy=accuracy if passed else None,
            # Keep duration on misses so Studio usage reflects real time on task.
            duration_seconds=duration_seconds,
            xp_awarded=awarded,
        )
    )
    await session.commit()
    return {
        "passed": passed,
        "failed_rule_hint": hint,
        "failed_kind": failed_kind,
        "xp_awarded": awarded,
        "xp_total": stats.xp,
        "hints_used": hints_used,
        **extra,
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
