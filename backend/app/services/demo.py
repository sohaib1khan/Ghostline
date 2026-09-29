"""Public demo catalog. Checks are not stored on an account."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.track import Track
from app.services.check_engine import check_attempt
from app.services.content_store import ContentError, learner_lesson


def _published_demo(lesson: Lesson) -> bool:
    return (
        lesson.is_demo
        and lesson.status == "published"
        and lesson.module.status == "published"
        and lesson.module.track.is_active
    )


def _demo_lessons(track: Track) -> list[dict]:
    lessons: list[dict] = []
    for module in track.modules:
        if module.status != "published":
            continue
        for lesson in module.lessons:
            if lesson.is_demo and lesson.status == "published":
                lessons.append({"id": lesson.id, "title": lesson.title, "summary": lesson.summary})
    return lessons


async def list_demo_tracks(session: AsyncSession) -> dict:
    rows = list(
        (
            await session.scalars(
                select(Track)
                .where(Track.is_active.is_(True))
                .options(selectinload(Track.modules).selectinload(Module.lessons))
                .order_by(Track.position)
            )
        ).all()
    )
    tracks = []
    for track in rows:
        lessons = _demo_lessons(track)
        if not lessons:
            continue
        tracks.append(
            {
                "slug": track.slug,
                "name": track.name,
                "description": track.description,
                "icon": track.icon,
                "color": track.color,
                "order": track.position,
                "lessons": lessons,
            }
        )
    return {"tracks": tracks}


async def demo_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> dict:
    row = await session.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.exercises),
            selectinload(Lesson.module).selectinload(Module.track),
        )
    )
    # DECISION: anything that is not a published demo answers 404, so drafts
    # and private lessons stay hidden from the public catalog.
    if row is None or not _published_demo(row):
        raise ContentError(404, "Lesson not found")
    visible = [item for item in row.exercises if item.status == "published"]
    return learner_lesson(row, visible)


async def demo_check(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    *,
    attempt: str,
    output: str | None,
) -> dict:
    row = await session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.lesson).selectinload(Lesson.module).selectinload(Module.track)
        )
    )
    if row is None or row.status != "published" or not _published_demo(row.lesson):
        raise ContentError(404, "Exercise not found")
    outcome = check_attempt(row.data or {}, attempt, output)
    # DECISION: a demo check is not saved. Account XP and streaks stay on
    # POST /api/check. The browser keeps demo progress in localStorage.
    return {
        "passed": outcome.passed,
        "failed_rule_hint": outcome.hint,
        "failed_kind": outcome.failed_kind,
        "xp_awarded": 0,
    }
