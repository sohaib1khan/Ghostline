"""Post-pass quiz checks — soft XP and mistake journal."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_log import AttemptLog
from app.models.content import Exercise
from app.models.practice import PracticeEvent
from app.models.progress import ExerciseProgress
from app.models.user import User
from app.services.content_store import ContentError
from app.services.progress import _stats_for
from app.services.review import schedule_after_result

QUIZ_XP = 2


def quiz_fingerprint(q: str, code: str = "") -> str:
    raw = f"{q}\0{code or ''}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def find_quiz_item(data: dict, *, q: str, code: str = "") -> dict | None:
    needle_q = str(q or "").strip()
    needle_code = str(code or "")
    for item in data.get("quiz") or []:
        if str(item.get("q") or "").strip() != needle_q:
            continue
        if str(item.get("code") or "") != needle_code:
            continue
        return item
    return None


async def record_quiz_result(
    session: AsyncSession,
    user: User,
    exercise_id: uuid.UUID,
    *,
    q: str,
    code: str,
    picked: str,
    first_try: bool,
) -> dict:
    exercise = await session.get(Exercise, exercise_id)
    if exercise is None:
        raise ContentError(404, "Exercise not found")
    item = find_quiz_item(exercise.data or {}, q=q, code=code)
    if item is None:
        raise ContentError(404, "Quiz question not found")

    answer = str(item.get("answer") or "")
    why = str(item.get("why") or "")
    passed = picked == answer
    fingerprint = quiz_fingerprint(q, code)
    awarded = 0

    progress = await session.scalar(
        select(ExerciseProgress).where(
            ExerciseProgress.user_id == user.id,
            ExerciseProgress.exercise_id == exercise.id,
        )
    )

    if passed and first_try:
        already = await session.scalar(
            select(AttemptLog.id).where(
                AttemptLog.user_id == user.id,
                AttemptLog.exercise_id == exercise.id,
                AttemptLog.passed.is_(True),
                AttemptLog.submitted == f"quiz-ok:{fingerprint}",
            )
        )
        if already is None:
            awarded = QUIZ_XP
            stats = await _stats_for(session, user.id)
            stats.xp += awarded
            session.add(
                PracticeEvent(
                    user_id=user.id,
                    exercise_id=exercise.id,
                    source="lesson",
                    passed=True,
                    xp_awarded=awarded,
                )
            )
            session.add(
                AttemptLog(
                    user_id=user.id,
                    exercise_id=exercise.id,
                    submitted=f"quiz-ok:{fingerprint}",
                    passed=True,
                    failed_rule_hint=None,
                    source="lesson",
                )
            )
    elif not passed:
        hint = f"Expected {answer}"[:500]
        if why:
            hint = f"{hint}. {why}"[:500]
        journal = (
            f"Q: {q}\n"
            f"Picked: {picked}\n"
            f"Answer: {answer}\n"
            f"Why: {why}"
        )[:4000]
        session.add(
            AttemptLog(
                user_id=user.id,
                exercise_id=exercise.id,
                submitted=journal,
                passed=False,
                failed_rule_hint=hint,
                source="lesson",
            )
        )
        # Queue the exercise for spaced review like other misses.
        if progress is not None and progress.status == "completed":
            review = schedule_after_result(
                interval_days=int(progress.interval_days or 0),
                ease=progress.ease or Decimal("2.50"),
                lapses=int(progress.lapses or 0),
                passed=False,
                hints_used=0,
                now=datetime.now(UTC),
            )
            progress.interval_days = review.interval_days
            progress.ease = review.ease
            progress.lapses = review.lapses
            progress.last_result = review.last_result
            progress.next_review_at = review.next_review_at

    await session.commit()
    stats = await _stats_for(session, user.id)
    return {
        "passed": passed,
        "answer": answer,
        "why": why,
        "xp_awarded": awarded,
        "xp_total": stats.xp,
    }
