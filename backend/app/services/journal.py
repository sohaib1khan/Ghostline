"""Mistake journal — usual slips and retention cleanup."""

from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_log import AttemptLog
from app.models.user import User

RETENTION_DAYS = 90
TOKEN_RE = re.compile(r"(?:^|\s)(-[A-Za-z0-9]+|--[A-Za-z0-9-]+|\b[a-z_]{2,}\b)")


async def usual_slips(session: AsyncSession, user: User, *, limit: int = 12) -> dict:
    since = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    rows = list(
        (
            await session.scalars(
                select(AttemptLog)
                .where(
                    AttemptLog.user_id == user.id,
                    AttemptLog.passed.is_(False),
                    AttemptLog.created_at >= since,
                )
                .order_by(AttemptLog.created_at.desc())
                .limit(500)
            )
        ).all()
    )
    hint_counts: Counter[str] = Counter()
    for row in rows:
        hint = (row.failed_rule_hint or "").strip()
        if hint:
            hint_counts[hint[:200]] += 1
            continue
        # Fall back to tokens present in accepted-looking hints from submitted text.
        for match in TOKEN_RE.findall(row.submitted or ""):
            token = match.strip()
            if token.startswith("-") or len(token) >= 3:
                hint_counts[f"Missed token around `{token}`"] += 1
    slips = [
        {"label": label, "count": count}
        for label, count in hint_counts.most_common(limit)
        if count >= 1
    ]
    return {"slips": slips, "attempts_scanned": len(rows), "retention_days": RETENTION_DAYS}


async def delete_journal(session: AsyncSession, user: User) -> dict:
    result = await session.execute(delete(AttemptLog).where(AttemptLog.user_id == user.id))
    await session.commit()
    return {"deleted": result.rowcount or 0}


async def purge_old_attempts(session: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    result = await session.execute(delete(AttemptLog).where(AttemptLog.created_at < cutoff))
    await session.commit()
    return result.rowcount or 0


async def struggling_exercise_ids(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 20
) -> list[uuid.UUID]:
    """Exercises with recent fails — preferred for review/games."""
    since = datetime.now(UTC) - timedelta(days=30)
    rows = list(
        (
            await session.execute(
                select(AttemptLog.exercise_id)
                .where(
                    AttemptLog.user_id == user_id,
                    AttemptLog.passed.is_(False),
                    AttemptLog.created_at >= since,
                )
                .order_by(AttemptLog.created_at.desc())
                .limit(limit * 3)
            )
        ).all()
    )
    seen: list[uuid.UUID] = []
    for (exercise_id,) in rows:
        if exercise_id not in seen:
            seen.append(exercise_id)
        if len(seen) >= limit:
            break
    return seen
