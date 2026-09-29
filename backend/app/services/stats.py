"""Trends for the signed-in learner."""

from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.practice import PracticeEvent
from app.models.progress import ExerciseProgress, UserStats
from app.models.user import User


async def learner_stats(session: AsyncSession, user: User) -> dict:
    stats = await session.scalar(select(UserStats).where(UserStats.user_id == user.id))
    completed = await session.scalar(
        select(func.count())
        .select_from(ExerciseProgress)
        .where(
            ExerciseProgress.user_id == user.id,
            ExerciseProgress.status == "completed",
        )
    )
    games = await session.scalar(
        select(func.count())
        .select_from(PracticeEvent)
        .where(PracticeEvent.user_id == user.id, PracticeEvent.source != "lesson")
    )
    trend_rows = list(
        (
            await session.execute(
                select(
                    cast(PracticeEvent.created_at, Date).label("day"),
                    func.round(func.avg(PracticeEvent.wpm)).label("wpm"),
                    func.round(func.avg(PracticeEvent.accuracy)).label("accuracy"),
                )
                .where(
                    PracticeEvent.user_id == user.id,
                    PracticeEvent.passed.is_(True),
                    PracticeEvent.wpm.is_not(None),
                )
                .group_by(cast(PracticeEvent.created_at, Date))
                .order_by(cast(PracticeEvent.created_at, Date))
            )
        ).all()
    )
    return {
        "xp": stats.xp if stats else 0,
        "current_streak_days": stats.current_streak_days if stats else 0,
        "longest_streak_days": stats.longest_streak_days if stats else 0,
        "exercises_completed": int(completed or 0),
        "games_played": int(games or 0),
        "wpm_trend": [
            {"day": _day(row.day), "wpm": int(row.wpm)} for row in trend_rows if row.wpm is not None
        ],
        "accuracy_trend": [
            {"day": _day(row.day), "accuracy": int(row.accuracy)}
            for row in trend_rows
            if row.accuracy is not None
        ],
    }


def _day(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
