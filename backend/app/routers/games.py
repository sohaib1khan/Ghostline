"""Practice games. Rounds come from published exercises the learner may open."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import current_user
from app.services.content_store import ContentError
from app.services.games import catalog, leaderboard, next_round, score_round

router = APIRouter(prefix="/games", tags=["games"])


class GameScore(BaseModel):
    game: str = Field(min_length=1, max_length=32)
    attempt: str = Field(default="", max_length=20000)
    output: str | None = Field(default=None, max_length=8000)
    wpm: int | None = Field(default=None, ge=0, le=400)
    accuracy: int | None = Field(default=None, ge=0, le=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    hints_used: int = Field(default=0, ge=0, le=16)
    letters: list[str] = Field(default_factory=list, max_length=64)
    phase: str = Field(default="submit", max_length=16)


@router.get("/catalog")
async def game_catalog(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await catalog(db, user)


@router.get("/next")
async def game_next(
    game: str = Query(min_length=1, max_length=32),
    track: str | None = Query(default=None, max_length=40),
    exclude: UUID | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await next_round(db, user, game, track, exclude)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/score/{exercise_id}")
async def game_score(
    exercise_id: UUID,
    body: GameScore,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await score_round(
            db,
            user,
            body.game,
            exercise_id,
            attempt=body.attempt,
            output=body.output,
            wpm=body.wpm,
            accuracy=body.accuracy,
            duration_seconds=body.duration_seconds,
            hints_used=body.hints_used,
            letters=body.letters,
            phase=body.phase,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/leaderboard")
async def game_leaderboard(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    del user
    try:
        return {"entries": await leaderboard(db)}
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
