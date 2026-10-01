"""Staff Leaderboard and usage insights."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.practice import PracticeEvent
from app.models.progress import ExerciseProgress, UserStats
from app.models.user import User


async def staff_insights(session: AsyncSession) -> dict:
    today = datetime.now(UTC).date()
    week_ago = today - timedelta(days=6)
    fortnight_ago = today - timedelta(days=13)

    approved = await session.scalar(
        select(func.count()).select_from(User).where(User.status == "approved")
    )
    pending = await session.scalar(
        select(func.count()).select_from(User).where(User.status == "pending")
    )
    total_xp = await session.scalar(select(func.coalesce(func.sum(UserStats.xp), 0)))
    completed = await session.scalar(
        select(func.count())
        .select_from(ExerciseProgress)
        .where(ExerciseProgress.status == "completed")
    )
    sessions = await session.scalar(select(func.count()).select_from(PracticeEvent))
    time_spent = await session.scalar(
        select(func.coalesce(func.sum(PracticeEvent.duration_seconds), 0)).where(
            PracticeEvent.duration_seconds.is_not(None)
        )
    )
    avg_wpm = await session.scalar(
        select(func.round(func.avg(PracticeEvent.wpm))).where(
            PracticeEvent.passed.is_(True),
            PracticeEvent.wpm.is_not(None),
        )
    )
    active_week = await session.scalar(
        select(func.count(func.distinct(PracticeEvent.user_id))).where(
            cast(PracticeEvent.created_at, Date) >= week_ago
        )
    )
    completed_week = await session.scalar(
        select(func.count())
        .select_from(ExerciseProgress)
        .where(
            ExerciseProgress.status == "completed",
            cast(ExerciseProgress.completed_at, Date) >= week_ago,
        )
    )

    activity_rows = list(
        (
            await session.execute(
                select(
                    cast(PracticeEvent.created_at, Date).label("day"),
                    func.count().label("events"),
                    func.count(func.distinct(PracticeEvent.user_id)).label("learners"),
                    func.coalesce(func.sum(PracticeEvent.duration_seconds), 0).label("seconds"),
                )
                .where(cast(PracticeEvent.created_at, Date) >= fortnight_ago)
                .group_by(cast(PracticeEvent.created_at, Date))
                .order_by(cast(PracticeEvent.created_at, Date))
            )
        ).all()
    )
    by_day = {
        _day(row.day): {
            "events": int(row.events or 0),
            "learners": int(row.learners or 0),
            "seconds": int(row.seconds or 0),
        }
        for row in activity_rows
    }
    activity = []
    cursor = fortnight_ago
    while cursor <= today:
        key = cursor.isoformat()
        bucket = by_day.get(key, {"events": 0, "learners": 0, "seconds": 0})
        activity.append({"day": key, **bucket})
        cursor += timedelta(days=1)

    source_rows = list(
        (
            await session.execute(
                select(PracticeEvent.source, func.count().label("count"))
                .group_by(PracticeEvent.source)
                .order_by(func.count().desc())
            )
        ).all()
    )
    sources = [{"source": row.source, "count": int(row.count or 0)} for row in source_rows]

    board = await _leaderboard_rows(session)
    return {
        "summary": {
            "approved_users": int(approved or 0),
            "pending_users": int(pending or 0),
            "active_learners_7d": int(active_week or 0),
            "total_xp": int(total_xp or 0),
            "exercises_completed": int(completed or 0),
            "exercises_completed_7d": int(completed_week or 0),
            "practice_sessions": int(sessions or 0),
            "time_spent_seconds": int(time_spent or 0),
            "avg_wpm": int(avg_wpm) if avg_wpm is not None else None,
        },
        "activity": activity,
        "sources": sources,
        "leaderboard": board,
    }


async def _leaderboard_rows(session: AsyncSession) -> list[dict]:
    users = list(
        (
            await session.scalars(
                select(User).where(User.status == "approved").order_by(User.created_at.asc())
            )
        ).all()
    )
    if not users:
        return []

    user_ids = [user.id for user in users]
    stats_rows = list(
        (await session.scalars(select(UserStats).where(UserStats.user_id.in_(user_ids)))).all()
    )
    stats_by = {row.user_id: row for row in stats_rows}

    completed_rows = list(
        (
            await session.execute(
                select(ExerciseProgress.user_id, func.count())
                .where(
                    ExerciseProgress.user_id.in_(user_ids),
                    ExerciseProgress.status == "completed",
                )
                .group_by(ExerciseProgress.user_id)
            )
        ).all()
    )
    completed_by = {user_id: int(count) for user_id, count in completed_rows}

    event_rows = list(
        (
            await session.execute(
                select(
                    PracticeEvent.user_id,
                    func.count().label("sessions"),
                    func.coalesce(
                        func.sum(case((PracticeEvent.source != "lesson", 1), else_=0)),
                        0,
                    ).label("games"),
                    func.coalesce(func.sum(PracticeEvent.duration_seconds), 0).label("seconds"),
                    func.round(func.avg(PracticeEvent.wpm)).label("avg_wpm"),
                    func.max(PracticeEvent.created_at).label("last_practice"),
                )
                .where(PracticeEvent.user_id.in_(user_ids))
                .group_by(PracticeEvent.user_id)
            )
        ).all()
    )
    events_by = {row.user_id: row for row in event_rows}

    rows = []
    for user in users:
        stats = stats_by.get(user.id)
        events = events_by.get(user.id)
        rows.append(
            {
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": user.role,
                "xp": int(stats.xp) if stats else 0,
                "current_streak_days": int(stats.current_streak_days) if stats else 0,
                "longest_streak_days": int(stats.longest_streak_days) if stats else 0,
                "last_active_date": (
                    stats.last_active_date.isoformat()
                    if stats and stats.last_active_date
                    else None
                ),
                "exercises_completed": completed_by.get(user.id, 0),
                "practice_sessions": int(events.sessions) if events else 0,
                "games_played": int(events.games) if events else 0,
                "time_spent_seconds": int(events.seconds) if events else 0,
                "avg_wpm": int(events.avg_wpm) if events and events.avg_wpm is not None else None,
                "last_practice_at": (
                    events.last_practice.isoformat() if events and events.last_practice else None
                ),
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            }
        )

    rows.sort(
        key=lambda item: (
            item["xp"],
            item["time_spent_seconds"],
            item["exercises_completed"],
            item["current_streak_days"],
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _day(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
