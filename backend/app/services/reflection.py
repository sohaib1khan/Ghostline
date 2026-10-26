"""Weekly learning reflection summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Exercise, Lesson, Module
from app.models.module_progress import ModuleProgress
from app.models.progress import ExerciseProgress
from app.models.track import Track
from app.models.user import User
from app.services.journal import usual_slips
from app.services.tracks import list_visible_tracks


async def weekly_reflection(session: AsyncSession, user: User) -> dict:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    next_week = now + timedelta(days=7)
    tracks = await list_visible_tracks(session, user)
    track_ids = [track.id for track in tracks]

    mastered_rows = []
    due_next = []
    if track_ids:
        mastered_rows = list(
            (
                await session.execute(
                    select(Module.title, Track.name, ModuleProgress.mastered_at)
                    .join(Module, Module.id == ModuleProgress.module_id)
                    .join(Track, Track.id == Module.track_id)
                    .where(
                        ModuleProgress.user_id == user.id,
                        ModuleProgress.mastered_at.is_not(None),
                        ModuleProgress.mastered_at >= week_ago,
                    )
                    .order_by(ModuleProgress.mastered_at.desc())
                )
            ).all()
        )
        due_next = list(
            (
                await session.execute(
                    select(
                        Exercise.id,
                        Lesson.title,
                        Module.title,
                        Track.name,
                        ExerciseProgress.next_review_at,
                    )
                    .join(Exercise, Exercise.id == ExerciseProgress.exercise_id)
                    .join(Lesson, Lesson.id == Exercise.lesson_id)
                    .join(Module, Module.id == Lesson.module_id)
                    .join(Track, Track.id == Module.track_id)
                    .where(
                        ExerciseProgress.user_id == user.id,
                        ExerciseProgress.next_review_at.is_not(None),
                        ExerciseProgress.next_review_at <= next_week,
                        Module.track_id.in_(track_ids),
                    )
                    .order_by(ExerciseProgress.next_review_at.asc())
                    .limit(20)
                )
            ).all()
        )

    slipping = await usual_slips(session, user, limit=5)
    return {
        "week_ending": now.date().isoformat(),
        "mastered": [
            {
                "module": title,
                "track": track_name,
                "mastered_at": stamp.isoformat() if stamp else None,
            }
            for title, track_name, stamp in mastered_rows
        ],
        "slipping": slipping.get("slips") or [],
        "due_next_week": [
            {
                "exercise_id": ex_id,
                "lesson": lesson_title,
                "module": module_title,
                "track": track_name,
                "next_review_at": due.isoformat() if due else None,
            }
            for ex_id, lesson_title, module_title, track_name, due in due_next
        ],
    }
