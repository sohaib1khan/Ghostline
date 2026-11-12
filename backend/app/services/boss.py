"""Module boss: server-side hints, checks, and honest credit scoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models.attempt_log import AttemptLog
from app.models.boss_run import BossRun
from app.models.content import Exercise, Lesson, Module
from app.models.progress import ExerciseProgress
from app.models.user import User
from app.services.check_engine import check_attempt, with_typed_language_normalize
from app.services.content_store import ContentError, _ghost_answer
from app.services.gating import (
    BOSS_PASS_MARK,
    RECALL_TYPES,
    assert_module_unlocked,
    ensure_module_row,
    pick_boss_exercises,
)

MAX_TRIES = 2
LEVEL_WORTH = {0: 1.0, 1: 0.9, 2: 0.75, 3: 0.5}
LEVEL_LABELS = {
    1: "Remind me",
    2: "What do I need?",
    3: "Show the shape",
}


def hint_worth(level: int) -> float:
    if level <= 0:
        return 1.0
    if level in LEVEL_WORTH:
        return LEVEL_WORTH[level]
    return 0.5


def item_credit(*, hint_level: int, tries: int, passed: bool, revealed: bool) -> float:
    if revealed or not passed:
        return 0.0
    worth = hint_worth(hint_level)
    if tries >= 2:
        return round(worth * 0.5, 4)
    return worth


def boss_hint_ladder(data: dict, *, lesson_title: str, lesson_summary: str) -> list[str]:
    authored = [str(item).strip() for item in (data.get("boss_hints") or []) if str(item).strip()]
    if authored:
        return authored[:6]
    ladder: list[str] = []
    title = (lesson_title or "this lesson").strip() or "this lesson"
    summary = (lesson_summary or "").strip()
    if summary:
        ladder.append(f'From the lesson "{title}": {summary}')
    else:
        ladder.append(f'From the lesson "{title}".')
    for hint in data.get("hints") or []:
        text = str(hint).strip()
        if text.startswith("You need:") or text.startswith("Plan ("):
            ladder.append(text)
            break
    return ladder[:6]


def hint_cost_rows(count: int) -> list[dict]:
    rows = []
    for level in range(1, count + 1):
        label = LEVEL_LABELS.get(level) or f"Hint {level}"
        rows.append(
            {
                "level": level,
                "label": label,
                "worth": hint_worth(level),
            }
        )
    return rows


def boss_safe_message(attempt: str, expected: str) -> str:
    """Line-based feedback that never quotes the accepted answer."""
    attempt_lines = attempt.splitlines() if attempt else [""]
    expected_lines = expected.splitlines() if expected else [""]
    limit = max(len(attempt_lines), len(expected_lines), 1)
    for index in range(limit):
        got = attempt_lines[index] if index < len(attempt_lines) else None
        want = expected_lines[index] if index < len(expected_lines) else None
        line_no = index + 1
        if got is None:
            return f"Line {line_no} is missing."
        if want is None:
            return f"Line {line_no} isn't needed."
        if got == want:
            continue
        if got.lstrip() == want.lstrip() and got != want:
            return f"Line {line_no} has the wrong indent."
        return f"Line {line_no} isn't right yet."
    return "Not quite — try again."


def _item_by_exercise(items: list[dict], exercise_id: uuid.UUID) -> dict | None:
    key = str(exercise_id)
    for item in items:
        if str(item.get("exercise_id")) == key:
            return item
    return None


async def _load_module(session: AsyncSession, module_id: uuid.UUID) -> Module:
    module = await session.scalar(
        select(Module)
        .where(Module.id == module_id)
        .options(selectinload(Module.lessons).selectinload(Lesson.exercises))
    )
    if module is None or module.status != "published":
        raise ContentError(404, "Module not found")
    return module


async def _load_run(session: AsyncSession, user: User, run_id: uuid.UUID) -> BossRun:
    run = await session.scalar(select(BossRun).where(BossRun.id == run_id))
    if run is None or run.user_id != user.id:
        raise ContentError(404, "Boss run not found")
    if run.finished_at is not None:
        raise ContentError(400, "This boss run is already finished")
    return run


async def _load_exercise_for_run(
    session: AsyncSession, run: BossRun, exercise_id: uuid.UUID
) -> tuple[Exercise, dict]:
    item = _item_by_exercise(list(run.items or []), exercise_id)
    if item is None:
        raise ContentError(400, "Exercise is not part of this boss run")
    exercise = await session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.lesson)
            .selectinload(Lesson.module)
            .selectinload(Module.track)
        )
    )
    if exercise is None:
        raise ContentError(404, "Exercise not found")
    return exercise, item


async def start_boss(session: AsyncSession, user: User, module_id: uuid.UUID) -> dict:
    module = await _load_module(session, module_id)
    await assert_module_unlocked(session, user, module)
    exercises = [
        exercise
        for lesson in module.lessons
        if lesson.status == "published"
        for exercise in lesson.exercises
        if exercise.status == "published" and exercise.type in RECALL_TYPES
    ]
    picked = pick_boss_exercises(exercises)
    if not picked:
        raise ContentError(400, "This module has no boss exercises yet")

    open_runs = list(
        (
            await session.scalars(
                select(BossRun).where(
                    BossRun.user_id == user.id,
                    BossRun.module_id == module_id,
                    BossRun.finished_at.is_(None),
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    for prior in open_runs:
        prior.finished_at = now

    items_state: list[dict] = []
    client_items: list[dict] = []
    for exercise in picked:
        data = dict(exercise.data or {})
        lesson = exercise.lesson
        ladder = boss_hint_ladder(
            data,
            lesson_title=lesson.title if lesson else "",
            lesson_summary=lesson.summary if lesson else "",
        )
        items_state.append(
            {
                "exercise_id": str(exercise.id),
                "hint_level": 0,
                "tries": 0,
                "passed": False,
                "revealed": False,
                "credit": None,
                "ended": False,
                "lesson_id": str(exercise.lesson_id),
            }
        )
        client_items.append(
            {
                "id": exercise.id,
                "prompt": data.get("prompt") or "Type the answer from memory.",
                "hint_count": len(ladder),
                "hint_costs": hint_cost_rows(len(ladder)),
                "lesson_id": exercise.lesson_id,
            }
        )

    run = BossRun(
        user_id=user.id,
        module_id=module_id,
        items=items_state,
        started_at=now,
        finished_at=None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    row = await ensure_module_row(session, user.id, module_id)
    return {
        "run_id": run.id,
        "module_id": module.id,
        "module_title": module.title,
        "pass_mark": BOSS_PASS_MARK,
        "mastered": bool(row.mastered_at),
        "boss_score": row.boss_score,
        "items": client_items,
        "count": len(client_items),
    }


async def open_hint(
    session: AsyncSession,
    user: User,
    module_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    exercise_id: uuid.UUID,
    level: int,
) -> dict:
    run = await _load_run(session, user, run_id)
    if run.module_id != module_id:
        raise ContentError(404, "Boss run not found")
    exercise, item = await _load_exercise_for_run(session, run, exercise_id)
    if item.get("ended"):
        raise ContentError(400, "This item is already finished")
    if level < 1:
        raise ContentError(400, "Hint level must be at least 1")
    current = int(item.get("hint_level") or 0)
    if level > current + 1:
        raise ContentError(400, "Open hints in order")
    data = dict(exercise.data or {})
    lesson = exercise.lesson
    ladder = boss_hint_ladder(
        data,
        lesson_title=lesson.title if lesson else "",
        lesson_summary=lesson.summary if lesson else "",
    )
    if level > len(ladder):
        raise ContentError(400, "That hint step does not exist")
    item["hint_level"] = max(current, level)
    # Persist JSONB mutation.
    items = list(run.items or [])
    for index, row in enumerate(items):
        if str(row.get("exercise_id")) == str(exercise_id):
            items[index] = item
            break
    run.items = items
    flag_modified(run, "items")
    await session.commit()
    return {
        "level": level,
        "text": ladder[level - 1],
        "hint_level": item["hint_level"],
        "worth": hint_worth(int(item["hint_level"])),
    }


async def _journal_and_review(
    session: AsyncSession,
    user: User,
    exercise: Exercise,
    *,
    attempt: str,
    passed: bool,
) -> None:
    session.add(
        AttemptLog(
            user_id=user.id,
            exercise_id=exercise.id,
            submitted=(attempt or "")[:4000],
            passed=passed,
            failed_rule_hint=None if passed else "Boss miss",
            source="boss",
        )
    )
    progress = await session.scalar(
        select(ExerciseProgress).where(
            ExerciseProgress.user_id == user.id,
            ExerciseProgress.exercise_id == exercise.id,
        )
    )
    if progress is not None and progress.status == "completed":
        from app.services.review import schedule_after_result

        review = schedule_after_result(
            interval_days=int(progress.interval_days or 0),
            ease=progress.ease or Decimal("2.50"),
            lapses=int(progress.lapses or 0),
            passed=passed,
            hints_used=0,
            now=datetime.now(UTC),
        )
        progress.interval_days = review.interval_days
        progress.ease = review.ease
        progress.lapses = review.lapses
        progress.last_result = review.last_result
        progress.next_review_at = review.next_review_at


def _persist_item(run: BossRun, exercise_id: uuid.UUID, item: dict) -> None:
    items = list(run.items or [])
    for index, row in enumerate(items):
        if str(row.get("exercise_id")) == str(exercise_id):
            items[index] = item
            break
    run.items = items
    flag_modified(run, "items")


async def check_boss_item(
    session: AsyncSession,
    user: User,
    module_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    exercise_id: uuid.UUID,
    attempt: str,
) -> dict:
    run = await _load_run(session, user, run_id)
    if run.module_id != module_id:
        raise ContentError(404, "Boss run not found")
    exercise, item = await _load_exercise_for_run(session, run, exercise_id)
    if item.get("ended"):
        raise ContentError(400, "This item is already finished")
    tries = int(item.get("tries") or 0)
    if tries >= MAX_TRIES:
        raise ContentError(400, "No tries left on this item")

    track_slug = None
    if exercise.lesson and exercise.lesson.module and exercise.lesson.module.track:
        track_slug = exercise.lesson.module.track.slug
    data = with_typed_language_normalize(dict(exercise.data or {}), track_slug)
    outcome = check_attempt(data, attempt, None)
    tries += 1
    item["tries"] = tries
    answer = _ghost_answer(data)
    safe = boss_safe_message(attempt, answer)

    if outcome.passed:
        credit = item_credit(
            hint_level=int(item.get("hint_level") or 0),
            tries=tries,
            passed=True,
            revealed=False,
        )
        item["passed"] = True
        item["credit"] = credit
        item["ended"] = True
        _persist_item(run, exercise_id, item)
        await _journal_and_review(session, user, exercise, attempt=attempt, passed=True)
        await session.commit()
        return {
            "passed": True,
            "tries_left": MAX_TRIES - tries,
            "credit": credit,
            "answer": answer,
            "message": "Correct",
            "ended": True,
            "lesson_id": exercise.lesson_id,
        }

    if tries < MAX_TRIES:
        _persist_item(run, exercise_id, item)
        await session.commit()
        return {
            "passed": False,
            "tries_left": MAX_TRIES - tries,
            "message": f"Not yet, one more try. Your second try is worth half. {safe}",
            "ended": False,
        }

    item["passed"] = False
    item["credit"] = 0.0
    item["ended"] = True
    _persist_item(run, exercise_id, item)
    await _journal_and_review(session, user, exercise, attempt=attempt, passed=False)
    await session.commit()
    return {
        "passed": False,
        "tries_left": 0,
        "credit": 0.0,
        "answer": answer,
        "message": safe,
        "ended": True,
        "lesson_id": exercise.lesson_id,
    }


async def reveal_boss_item(
    session: AsyncSession,
    user: User,
    module_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    exercise_id: uuid.UUID,
) -> dict:
    run = await _load_run(session, user, run_id)
    if run.module_id != module_id:
        raise ContentError(404, "Boss run not found")
    exercise, item = await _load_exercise_for_run(session, run, exercise_id)
    if item.get("ended"):
        raise ContentError(400, "This item is already finished")
    data = dict(exercise.data or {})
    answer = _ghost_answer(data)
    item["revealed"] = True
    item["passed"] = False
    item["credit"] = 0.0
    item["ended"] = True
    _persist_item(run, exercise_id, item)
    await _journal_and_review(session, user, exercise, attempt="", passed=False)
    await session.commit()
    return {
        "passed": False,
        "credit": 0.0,
        "answer": answer,
        "message": "Answer revealed. This item scores 0.",
        "ended": True,
        "lesson_id": exercise.lesson_id,
    }


async def finish_boss(
    session: AsyncSession,
    user: User,
    module_id: uuid.UUID,
    run_id: uuid.UUID,
) -> dict:
    run = await session.scalar(select(BossRun).where(BossRun.id == run_id))
    if run is None or run.user_id != user.id or run.module_id != module_id:
        raise ContentError(404, "Boss run not found")
    if run.finished_at is not None:
        raise ContentError(400, "This boss run is already finished")

    items = list(run.items or [])
    if not items:
        raise ContentError(400, "This boss run has no items")
    if any(not item.get("ended") for item in items):
        raise ContentError(400, "Finish every item before ending the boss")

    total = len(items)
    earned = sum(float(item.get("credit") or 0.0) for item in items)
    ratio = earned / total if total else 0.0
    score_pct = round(100 * ratio)
    mastered = ratio >= BOSS_PASS_MARK

    breakdown = []
    for item in items:
        hint_level = int(item.get("hint_level") or 0)
        credit = float(item.get("credit") or 0.0)
        passed = bool(item.get("passed"))
        breakdown.append(
            {
                "exercise_id": item.get("exercise_id"),
                "passed": passed,
                "hint_level": hint_level,
                "tries": int(item.get("tries") or 0),
                "revealed": bool(item.get("revealed")),
                "credit": credit,
                "mastered_without_hints": passed and hint_level == 0 and not item.get("revealed"),
            }
        )

    run.finished_at = datetime.now(UTC)
    row = await ensure_module_row(session, user.id, module_id)
    row.boss_attempts = int(row.boss_attempts or 0) + 1
    row.boss_score = score_pct
    if mastered and row.mastered_at is None:
        row.mastered_at = datetime.now(UTC)
    await session.commit()

    return {
        "passed": mastered,
        "score": score_pct,
        "pass_mark": int(BOSS_PASS_MARK * 100),
        "mastered": bool(row.mastered_at),
        "mastered_at": row.mastered_at.isoformat() if row.mastered_at else None,
        "earned": round(earned, 4),
        "total": total,
        "items": breakdown,
        "mastered_without_hints": all(entry["mastered_without_hints"] for entry in breakdown),
    }
