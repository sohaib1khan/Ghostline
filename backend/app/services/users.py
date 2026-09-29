"""Admin changes to accounts. Passwords never appear in the audit log."""

import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, UserTrackAccess
from app.models.user import User
from app.security.passwords import hash_password, validate_password
from app.services.audit import write_audit
from app.services.auth import revoke_user_sessions
from app.services.notifications.dispatcher import dispatch_event

# Separate from the setup lock so the two flows do not block each other.
ADMIN_LOCK_ID = 4815162343


class UserAdminError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def user_summary(user: User, track_slugs: list[str]) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "status": user.status,
        "track_slugs": track_slugs,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


async def track_slugs_for(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    grouped: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
    if not user_ids:
        return grouped
    rows = await session.execute(
        select(UserTrackAccess.user_id, Track.slug)
        .join(Track, Track.id == UserTrackAccess.track_id)
        .where(UserTrackAccess.user_id.in_(user_ids))
        .order_by(Track.position, Track.slug)
    )
    for user_id, slug in rows:
        grouped[user_id].append(slug)
    return grouped


async def list_users(session: AsyncSession, status: str | None) -> list[dict]:
    stmt = select(User).order_by(User.created_at.desc())
    if status is not None:
        stmt = stmt.where(User.status == status)
    users = list((await session.scalars(stmt)).all())
    slugs = await track_slugs_for(session, [user.id for user in users])
    return [user_summary(user, slugs[user.id]) for user in users]


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise UserAdminError(404, "User not found")
    return user


async def _summary(session: AsyncSession, user: User) -> dict:
    slugs = await track_slugs_for(session, [user.id])
    return user_summary(user, slugs[user.id])


async def replace_track_access(
    session: AsyncSession, user_id: uuid.UUID, slugs: list[str]
) -> list[str]:
    if not slugs:
        await session.execute(delete(UserTrackAccess).where(UserTrackAccess.user_id == user_id))
        return []
    tracks = list(
        (
            await session.scalars(
                select(Track).where(Track.slug.in_(slugs), Track.is_active.is_(True))
            )
        ).all()
    )
    if len(tracks) != len(slugs):
        raise UserAdminError(400, "Unknown track")
    await session.execute(delete(UserTrackAccess).where(UserTrackAccess.user_id == user_id))
    by_slug = {track.slug: track for track in tracks}
    for slug in slugs:
        session.add(UserTrackAccess(user_id=user_id, track_id=by_slug[slug].id))
    return list(slugs)


async def _lock_admin_changes(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": ADMIN_LOCK_ID},
    )


async def _keep_an_admin(session: AsyncSession, user: User, *, role: str, status: str) -> None:
    remains = role == "admin" and status == "approved"
    if user.role != "admin" or user.status != "approved" or remains:
        return
    others = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.status == "approved", User.id != user.id)
    )
    if not others:
        raise UserAdminError(409, "The last admin cannot be removed")


async def create_user(
    session: AsyncSession,
    *,
    actor: User,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    role: str,
    track_slugs: list[str],
    ip: str | None,
) -> dict:
    normalized = email.strip().lower()
    try:
        validate_password(password, normalized)
    except ValueError as exc:
        raise UserAdminError(400, str(exc)) from exc
    taken = await session.scalar(select(User.id).where(User.email == normalized))
    if taken is not None:
        raise UserAdminError(409, "A user with that email already exists")
    user = User(
        email=normalized,
        first_name=first_name,
        last_name=last_name,
        password_hash=hash_password(password),
        role=role,
        status="approved",
        failed_login_count=0,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise UserAdminError(409, "A user with that email already exists") from exc
    slugs = await replace_track_access(session, user.id, track_slugs)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        details={"email": normalized, "role": role, "track_slugs": slugs},
        ip=ip,
    )
    await session.commit()
    return user_summary(user, slugs)


async def update_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    role: str | None,
    status: str | None,
    ip: str | None,
) -> dict:
    if actor.id == user_id:
        raise UserAdminError(409, "You cannot change your own access")
    # current_user already started this session's transaction, so begin() would fail.
    await _lock_admin_changes(session)
    user = await _load_user(session, user_id)
    next_role = role or user.role
    next_status = status or user.status
    await _keep_an_admin(session, user, role=next_role, status=next_status)
    user.role = next_role
    user.status = next_status
    if next_status != "approved":
        await revoke_user_sessions(session, user.id)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        details={"role": next_role, "status": next_status},
        ip=ip,
    )
    await session.commit()
    return await _summary(session, user)


async def approve_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    track_slugs: list[str],
    ip: str | None,
) -> dict:
    if actor.id == user_id:
        raise UserAdminError(409, "You cannot change your own access")
    await _lock_admin_changes(session)
    user = await _load_user(session, user_id)
    user.status = "approved"
    slugs = await replace_track_access(session, user.id, track_slugs)
    email = user.email
    first_name = user.first_name
    last_name = user.last_name
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.approve",
        target_type="user",
        target_id=str(user.id),
        details={"email": email, "track_slugs": slugs},
        ip=ip,
    )
    await session.commit()
    await dispatch_event(
        "user.approved",
        {"email": email, "first_name": first_name, "last_name": last_name},
    )
    return await _summary(session, user)


async def reject_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    if actor.id == user_id:
        raise UserAdminError(409, "You cannot change your own access")
    await _lock_admin_changes(session)
    user = await _load_user(session, user_id)
    await _keep_an_admin(session, user, role=user.role, status="rejected")
    user.status = "rejected"
    await session.execute(delete(UserTrackAccess).where(UserTrackAccess.user_id == user.id))
    await revoke_user_sessions(session, user.id)
    email = user.email
    first_name = user.first_name
    last_name = user.last_name
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.reject",
        target_type="user",
        target_id=str(user.id),
        details={"email": email},
        ip=ip,
    )
    await session.commit()
    await dispatch_event(
        "user.rejected",
        {"email": email, "first_name": first_name, "last_name": last_name},
    )
    return await _summary(session, user)


async def set_tracks(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    track_slugs: list[str],
    ip: str | None,
) -> dict:
    user = await _load_user(session, user_id)
    slugs = await replace_track_access(session, user.id, track_slugs)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.tracks",
        target_type="user",
        target_id=str(user.id),
        details={"track_slugs": slugs},
        ip=ip,
    )
    await session.commit()
    return await _summary(session, user)


async def reset_password(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    password: str,
    ip: str | None,
) -> None:
    user = await _load_user(session, user_id)
    try:
        validate_password(password, user.email)
    except ValueError as exc:
        raise UserAdminError(400, str(exc)) from exc
    user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    await revoke_user_sessions(session, user.id)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.reset_password",
        target_type="user",
        target_id=str(user.id),
        details={},
        ip=ip,
    )
    await session.commit()


async def revoke_sessions(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    ip: str | None,
) -> None:
    user = await _load_user(session, user_id)
    await revoke_user_sessions(session, user.id)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="user.revoke_sessions",
        target_type="user",
        target_id=str(user.id),
        details={},
        ip=ip,
    )
    await session.commit()
