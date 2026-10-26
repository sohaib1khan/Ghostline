"""Mastery gates: unlock next module at 80% recall, boss for mastery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.module_progress import ModuleProgress
from app.models.progress import ExerciseProgress
from app.models.user import User
from app.services.audit import write_audit
from app.services.content_store import ContentError

RECALL_TYPES = frozenset({"recall", "challenge"})
PRACTICE_TYPES = frozenset({"trace", "fill"})
UNLOCK_THRESHOLD = 0.80
BOSS_PASS_MARK = 0.70
BOSS_SIZE_MIN = 5
BOSS_SIZE_MAX = 8


def lesson_progress_label(
    exercises: list[tuple[str, str | None]],
) -> str:
    """Map exercise (type, status) pairs to new | practiced | started | done.

    A lesson is *done* only when every recall/challenge is completed.
    Trace/fill alone yield *practiced*.
    """
    if not exercises:
        return "new"
    recall = [(etype, status) for etype, status in exercises if etype in RECALL_TYPES]
    practice = [(etype, status) for etype, status in exercises if etype in PRACTICE_TYPES]
    if recall:
        if all(status == "completed" for _etype, status in recall):
            return "done"
        if any(status for _etype, status in recall) or any(status for _etype, status in practice):
            if any(status == "completed" for _etype, status in practice) and not any(
                status == "completed" for _etype, status in recall
            ):
                return "practiced"
            return "started"
        if any(status == "completed" for _etype, status in practice):
            return "practiced"
        return "new"
    # No recall exercises — fall back to all exercises.
    if all(status == "completed" for _etype, status in exercises):
        return "done"
    if any(status for _etype, status in exercises):
        return "started"
    return "new"


def unlock_needed(recall_total: int, recall_done: int) -> dict:
    """How many more recalls to unlock the next module."""
    import math

    if recall_total <= 0:
        return {
            "ready": True,
            "needed": 0,
            "done": 0,
            "total": 0,
            "threshold": 0,
            "pct": 100,
        }
    threshold = math.ceil(recall_total * UNLOCK_THRESHOLD)
    needed = max(0, threshold - recall_done)
    pct = round(100 * recall_done / recall_total)
    return {
        "ready": recall_done >= threshold,
        "needed": needed,
        "done": recall_done,
        "total": recall_total,
        "threshold": threshold,
        "pct": pct,
    }


async def _module_rows(session: AsyncSession, track_id: uuid.UUID) -> list[Module]:
    return list(
        (
            await session.scalars(
                select(Module)
                .where(Module.track_id == track_id, Module.status == "published")
                .options(
                    selectinload(Module.lessons).selectinload(Lesson.exercises),
                )
                .order_by(Module.position)
            )
        ).all()
    )


async def _progress_map(
    session: AsyncSession, user_id: uuid.UUID, exercise_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
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
    return {row.exercise_id: row.status for row in rows}


async def _module_progress_map(
    session: AsyncSession, user_id: uuid.UUID, module_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ModuleProgress]:
    if not module_ids:
        return {}
    rows = list(
        (
            await session.scalars(
                select(ModuleProgress).where(
                    ModuleProgress.user_id == user_id,
                    ModuleProgress.module_id.in_(module_ids),
                )
            )
        ).all()
    )
    return {row.module_id: row for row in rows}


async def ensure_module_row(
    session: AsyncSession, user_id: uuid.UUID, module_id: uuid.UUID
) -> ModuleProgress:
    row = await session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.module_id == module_id,
        )
    )
    if row is None:
        row = ModuleProgress(
            user_id=user_id,
            module_id=module_id,
            unlocked=False,
            unlocked_by_admin=False,
            boss_attempts=0,
        )
        session.add(row)
        await session.flush()
    return row


def _recall_stats(module: Module, status_by_ex: dict[uuid.UUID, str]) -> dict:
    recalls: list[Exercise] = []
    for lesson in module.lessons:
        if lesson.status != "published":
            continue
        for exercise in lesson.exercises:
            if exercise.status != "published":
                continue
            if exercise.type in RECALL_TYPES:
                recalls.append(exercise)
    done = sum(1 for item in recalls if status_by_ex.get(item.id) == "completed")
    return unlock_needed(len(recalls), done)


async def module_gate_state(
    session: AsyncSession, user: User, track_id: uuid.UUID
) -> list[dict]:
    """Return unlock/mastery info for each published module in order."""
    modules = await _module_rows(session, track_id)
    exercise_ids = [
        exercise.id
        for module in modules
        for lesson in module.lessons
        if lesson.status == "published"
        for exercise in lesson.exercises
        if exercise.status == "published"
    ]
    status_by_ex = await _progress_map(session, user.id, exercise_ids)
    mp_map = await _module_progress_map(session, user.id, [m.id for m in modules])

    states: list[dict] = []
    prev_unlocks_next = True  # first module always opens
    for index, module in enumerate(modules):
        stats = _recall_stats(module, status_by_ex)
        row = mp_map.get(module.id)
        admin_unlocked = bool(row and row.unlocked_by_admin)
        already = bool(row and row.unlocked)
        is_first = index == 0
        unlocked = is_first or admin_unlocked or already or prev_unlocks_next
        if unlocked:
            row = await ensure_module_row(session, user.id, module.id)
            if not row.unlocked:
                row.unlocked = True
                mp_map[module.id] = row

        mastered = bool(row and row.mastered_at)
        lock_reason = None
        if not unlocked and index > 0:
            prev = states[index - 1]
            needed = prev.get("needed") or 0
            lock_reason = (
                f"Pass {needed} more recalls in {prev['title']}"
                if needed
                else f"Finish unlocking work in {prev['title']}"
            )
        states.append(
            {
                "module_id": module.id,
                "title": module.title,
                "unlocked": unlocked,
                "mastered": mastered,
                "boss_score": row.boss_score if row else None,
                "recall_done": stats["done"],
                "recall_total": stats["total"],
                "recall_pct": stats["pct"],
                "unlock_ready": stats["ready"],
                "needed": stats["needed"],
                "lock_reason": lock_reason,
            }
        )
        # Next module opens when this one hits 80% recall, is mastered, or admin-unlocked.
        prev_unlocks_next = bool(stats["ready"] or mastered or admin_unlocked)

    await session.flush()
    return states


async def assert_module_unlocked(
    session: AsyncSession, user: User, module: Module
) -> None:
    from app.security.roles import is_staff

    if is_staff(user.role):
        return
    states = await module_gate_state(session, user, module.track_id)
    match = next((item for item in states if item["module_id"] == module.id), None)
    if match is None or not match["unlocked"]:
        reason = (match or {}).get("lock_reason") or "This module is locked"
        # Prefer previous module's needed count for a clearer message.
        idx = next((i for i, item in enumerate(states) if item["module_id"] == module.id), -1)
        if idx > 0:
            prev = states[idx - 1]
            needed = prev.get("needed") or 0
            if needed > 0:
                reason = f"Pass {needed} more recalls in {prev['title']}"
        raise ContentError(403, reason)


async def admin_unlock_module(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    module_id: uuid.UUID,
    ip: str | None = None,
) -> dict:
    module = await session.scalar(select(Module).where(Module.id == module_id))
    if module is None:
        raise ContentError(404, "Module not found")
    row = await ensure_module_row(session, user_id, module_id)
    row.unlocked = True
    row.unlocked_by_admin = True
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="module.unlock",
        target_type="module",
        target_id=str(module_id),
        details={"user_id": str(user_id), "module_title": module.title},
        ip=ip,
    )
    await session.commit()
    return {"module_id": module_id, "user_id": user_id, "unlocked": True}


def pick_boss_exercises(exercises: list[Exercise], *, limit: int = BOSS_SIZE_MAX) -> list[Exercise]:
    """Prefer recalls; pad with challenges; cap 5–8."""
    recalls = [item for item in exercises if item.type == "recall"]
    challenges = [item for item in exercises if item.type == "challenge"]
    picked = (recalls + challenges)[:limit]
    if len(picked) < BOSS_SIZE_MIN:
        return picked
    return picked[: max(BOSS_SIZE_MIN, min(limit, len(picked)))]


async def boss_payload(session: AsyncSession, user: User, module_id: uuid.UUID) -> dict:
    module = await session.scalar(
        select(Module)
        .where(Module.id == module_id)
        .options(selectinload(Module.lessons).selectinload(Lesson.exercises))
    )
    if module is None or module.status != "published":
        raise ContentError(404, "Module not found")
    await assert_module_unlocked(session, user, module)
    exercises = [
        exercise
        for lesson in module.lessons
        if lesson.status == "published"
        for exercise in lesson.exercises
        if exercise.status == "published" and exercise.type in RECALL_TYPES
    ]
    picked = pick_boss_exercises(exercises)
    from app.services.content_store import _ghost_answer

    items = []
    for exercise in picked:
        data = dict(exercise.data or {})
        items.append(
            {
                "id": exercise.id,
                "type": "recall",
                "prompt": data.get("prompt") or "Type the answer from memory.",
                "ghost": _ghost_answer(data),
                "hints": [],  # boss: no hints
                "xp": data.get("xp", 0),
            }
        )
    row = await ensure_module_row(session, user.id, module_id)
    return {
        "module_id": module.id,
        "module_title": module.title,
        "pass_mark": BOSS_PASS_MARK,
        "mastered": bool(row.mastered_at),
        "boss_score": row.boss_score,
        "items": items,
        "count": len(items),
    }


async def submit_boss(
    session: AsyncSession,
    user: User,
    module_id: uuid.UUID,
    *,
    results: list[dict],
) -> dict:
    """results: [{exercise_id, passed}] — graded client-side via check API already,
    or we re-check. Here we trust passed flags only after individual checks;
    acceptance uses score ratio.
    """
    payload = await boss_payload(session, user, module_id)
    if not payload["items"]:
        raise ContentError(400, "This module has no boss exercises yet")
    by_id = {item["id"]: item for item in payload["items"]}
    passed = 0
    total = len(by_id)
    for entry in results:
        ex_id = entry.get("exercise_id")
        if ex_id in by_id and entry.get("passed"):
            passed += 1
    score_pct = round(100 * passed / total) if total else 0
    ratio = passed / total if total else 0
    row = await ensure_module_row(session, user.id, module_id)
    row.boss_attempts = int(row.boss_attempts or 0) + 1
    row.boss_score = score_pct
    mastered = ratio >= BOSS_PASS_MARK
    if mastered and row.mastered_at is None:
        row.mastered_at = datetime.now(UTC)
    await session.commit()
    return {
        "passed": mastered,
        "score": score_pct,
        "pass_mark": int(BOSS_PASS_MARK * 100),
        "mastered": bool(row.mastered_at),
        "mastered_at": row.mastered_at.isoformat() if row.mastered_at else None,
    }
