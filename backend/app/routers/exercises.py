"""Learner exercise helpers (walkthrough / step-through)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.attempt_log import AttemptLog
from app.models.content import Exercise
from app.models.user import User
from app.security.deps import current_user
from app.security.rate_limit import limiter
from app.services.content_store import ContentError
from app.services.walkthrough import walkthrough_for_user

router = APIRouter(prefix="/exercises", tags=["exercises"])


class PredictMissIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    guessed: str = Field(default="", max_length=200)
    expected: str = Field(default="", max_length=200)


@router.get("/{exercise_id}/walkthrough")
@limiter.limit("60/minute")
async def get_walkthrough(
    request: Request,
    exercise_id: UUID,
    hints_opened: int = Query(default=0, ge=0, le=50),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await walkthrough_for_user(
            db, user, exercise_id, hints_opened=hints_opened
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{exercise_id}/walkthrough/predict-miss")
@limiter.limit("30/minute")
async def log_predict_miss(
    request: Request,
    exercise_id: UUID,
    body: PredictMissIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft mistake-journal entry when a walkthrough prediction is wrong. No XP."""
    exercise = await db.get(Exercise, exercise_id)
    if exercise is None or not (exercise.data or {}).get("walkthrough"):
        raise HTTPException(status_code=404, detail="Exercise not found")
    db.add(
        AttemptLog(
            user_id=user.id,
            exercise_id=exercise_id,
            submitted=f"predicted {body.name}={body.guessed}"[:4000],
            passed=False,
            failed_rule_hint=f"Expected {body.expected}"[:500],
            source="lesson",
        )
    )
    await db.commit()
    return {"ok": True}
