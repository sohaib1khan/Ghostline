"""Compare a learner's answer. The code itself is never executed."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.progress import CheckSubmit
from app.security.deps import current_user
from app.services.content_store import ContentError
from app.services.progress import submit_check

router = APIRouter(prefix="/check", tags=["check"])


@router.post("/{exercise_id}")
async def check_exercise(
    exercise_id: UUID,
    body: CheckSubmit,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await submit_check(
            db,
            user,
            exercise_id,
            attempt=body.attempt,
            output=body.output,
            hints_used=body.hints_used,
            wpm=body.wpm,
            accuracy=body.accuracy,
            duration_seconds=body.duration_seconds,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
