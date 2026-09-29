"""Public demo catalog and checks. No account is required."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.schemas.progress import CheckSubmit
from app.security.rate_limit import limiter
from app.services.content_store import ContentError
from app.services.demo import demo_check, demo_lesson, list_demo_tracks

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/tracks")
async def tracks(db: AsyncSession = Depends(get_db)) -> dict:
    return await list_demo_tracks(db)


@router.get("/lessons/{lesson_id}")
async def lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await demo_lesson(db, lesson_id)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/check/{exercise_id}")
@limiter.limit(lambda: f"{get_settings().rate_limit_demo_check}/minute")
async def check_demo(
    request: Request,
    exercise_id: UUID,
    body: CheckSubmit,
    db: AsyncSession = Depends(get_db),
) -> dict:
    del request
    try:
        return await demo_check(
            db,
            exercise_id,
            attempt=body.attempt,
            output=body.output,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
