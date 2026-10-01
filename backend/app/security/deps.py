"""Load the current user from the session cookie."""

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.session import UserSession
from app.models.track import Track, UserTrackAccess
from app.models.user import User
from app.security.cookies import SESSION_COOKIE
from app.security.tokens import hash_token

UNAUTHORIZED = HTTPException(status_code=401, detail="Not signed in")
FORBIDDEN = HTTPException(status_code=403, detail="Admin access is required")
SUPER_FORBIDDEN = HTTPException(status_code=403, detail="Super admin access is required")


async def current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise UNAUTHORIZED
    now = datetime.now(UTC)
    row = await db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw)))
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise UNAUTHORIZED
    user = await db.get(User, row.user_id)
    if user is None or user.status != "approved":
        raise UNAUTHORIZED
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    from app.security.roles import is_staff

    if not is_staff(user.role):
        raise FORBIDDEN
    return user


async def require_super_admin(user: User = Depends(current_user)) -> User:
    from app.security.roles import is_super_admin

    if not is_super_admin(user.role):
        raise SUPER_FORBIDDEN
    return user


async def require_track_access(
    slug: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Track:
    from app.security.roles import is_staff

    track = await db.scalar(select(Track).where(Track.slug == slug, Track.is_active.is_(True)))
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    if is_staff(user.role):
        return track
    access = await db.scalar(
        select(UserTrackAccess.id).where(
            UserTrackAccess.user_id == user.id,
            UserTrackAccess.track_id == track.id,
        )
    )
    if access is None:
        raise HTTPException(status_code=403, detail="You do not have access to this track")
    return track
