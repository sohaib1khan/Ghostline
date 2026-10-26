"""Spaced review queue for signed-in learners."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.content import Exercise, Lesson, Module
from app.models.progress import ExerciseProgress
from app.models.track import Track
from app.models.user import User
from app.security.deps import current_user
from app.services.content_store import ContentError, _ghost_answer, _practice_hints
from app.services.progress import submit_check
from app.services.tracks import list_visible_tracks

router = APIRouter(prefix="/review", tags=["review"])

DEFAULT_DAILY_CAP = 30


class ReviewSubmitIn(BaseModel):
    attempt: str = Field(default="", max_length=20000)
    hints_used: int = Field(default=0, ge=0, le=50)
    wpm: int | None = Field(default=None, ge=0, le=400)
    accuracy: int | None = Field(default=None, ge=0, le=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    # guessed | unsure | knew — guessed passes schedule like pass_hints
    confidence: str | None = Field(default=None, pattern="^(guessed|unsure|knew)?$")


def _as_recall_payload(exercise: Exercise, track: Track, module: Module, lesson: Lesson) -> dict:
    data = dict(exercise.data or {})
    ghost = _ghost_answer(data)
    return {
        "id": exercise.id,
        "type": "recall",
        "prompt": data.get("prompt") or "Type the answer from memory.",
        "runtime": data.get("runtime") or "none",
        "code": "",
        "ghost": ghost,
        "tokens": [],
        "blanks": [],
        "hints": _practice_hints("recall", data),
        "xp": data.get("xp", 0),
        "track_slug": track.slug,
        "track_name": track.name,
        "lesson_title": lesson.title,
        "module_title": module.title,
        "next_review_at": None,
    }


@router.get("/due")
async def due_reviews(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    now = datetime.now(UTC)
    tracks = await list_visible_tracks(db, user)
    track_ids = {track.id for track in tracks}
    if not track_ids:
        return {"due": [], "count": 0, "daily_cap": DEFAULT_DAILY_CAP, "estimate_minutes": 0}

    result = await db.execute(
        select(ExerciseProgress, Exercise, Lesson, Module, Track)
        .join(Exercise, Exercise.id == ExerciseProgress.exercise_id)
        .join(Lesson, Lesson.id == Exercise.lesson_id)
        .join(Module, Module.id == Lesson.module_id)
        .join(Track, Track.id == Module.track_id)
        .where(
            ExerciseProgress.user_id == user.id,
            ExerciseProgress.status == "completed",
            ExerciseProgress.next_review_at.is_not(None),
            ExerciseProgress.next_review_at <= now,
            Module.track_id.in_(track_ids),
            Exercise.status == "published",
            Lesson.status == "published",
            Module.status == "published",
        )
        .order_by(ExerciseProgress.next_review_at.asc())
        .limit(min(limit, DEFAULT_DAILY_CAP))
    )
    rows = list(result.all())
    # Prefer journal struggles first, then interleave by track.
    from app.services.journal import struggling_exercise_ids

    struggle_ids = set(await struggling_exercise_ids(db, user.id))
    struggle_rows = [row for row in rows if row[1].id in struggle_ids]
    other_rows = [row for row in rows if row[1].id not in struggle_ids]
    ordered = struggle_rows + other_rows

    by_track: dict[str, list] = {}
    for progress, exercise, lesson, module, track in ordered:
        by_track.setdefault(track.slug, []).append((progress, exercise, lesson, module, track))
    mixed: list = []
    while any(by_track.values()):
        for slug in list(by_track.keys()):
            bucket = by_track.get(slug) or []
            if not bucket:
                by_track.pop(slug, None)
                continue
            mixed.append(bucket.pop(0))
            if not bucket:
                by_track.pop(slug, None)

    due = []
    for progress, exercise, lesson, module, track in mixed:
        item = _as_recall_payload(exercise, track, module, lesson)
        item["next_review_at"] = (
            progress.next_review_at.isoformat() if progress.next_review_at else None
        )
        due.append(item)
    estimate = max(1, round(len(due) * 0.5)) if due else 0
    return {
        "due": due,
        "count": len(due),
        "daily_cap": DEFAULT_DAILY_CAP,
        "estimate_minutes": estimate,
    }


@router.post("/{exercise_id}")
async def submit_review(
    exercise_id: uuid.UUID,
    payload: ReviewSubmitIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Guessed passes count like passes with hints for scheduling.
    hints = payload.hints_used
    if payload.confidence == "guessed" and hints == 0:
        hints = max(hints, 1)
    try:
        result = await submit_check(
            db,
            user,
            exercise_id,
            attempt=payload.attempt,
            output=None,
            wpm=payload.wpm,
            accuracy=payload.accuracy,
            hints_used=hints,
            duration_seconds=payload.duration_seconds,
            source="review",
        )
        result["confidence"] = payload.confidence
        return result
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
