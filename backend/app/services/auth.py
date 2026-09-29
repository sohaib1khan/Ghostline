"""Login, logout, and lockout. Failures share one generic message."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.session import UserSession
from app.models.user import User
from app.security.passwords import dummy_password_hash, verify_password
from app.security.tokens import hash_token, new_token
from app.services.audit import write_audit

GENERIC_LOGIN_ERROR = "Invalid email or password"
PENDING_LOGIN_MESSAGE = "Your account is waiting for an admin to approve access."
REJECTED_LOGIN_MESSAGE = "This account was not approved. An admin can review the request."
DISABLED_LOGIN_MESSAGE = "This account is disabled."
STATUS_LOGIN_MESSAGES = {
    "pending": PENDING_LOGIN_MESSAGE,
    "rejected": REJECTED_LOGIN_MESSAGE,
    "disabled": DISABLED_LOGIN_MESSAGE,
}
LOCKOUT_THRESHOLD = 5
LOCKOUT_BASE_SECONDS = 30
LOCKOUT_MAX_SECONDS = 15 * 60


class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 401) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def lock_duration(failed_count: int) -> timedelta | None:
    """Backoff starts at the fifth failure and doubles, capped at 15 minutes."""
    if failed_count < LOCKOUT_THRESHOLD:
        return None
    exponent = failed_count - LOCKOUT_THRESHOLD
    seconds = min(LOCKOUT_BASE_SECONDS * (2**exponent), LOCKOUT_MAX_SECONDS)
    return timedelta(seconds=seconds)


async def _record_failure(session: AsyncSession, user: User) -> None:
    user.failed_login_count += 1
    duration = lock_duration(user.failed_login_count)
    user.locked_until = datetime.now(UTC) + duration if duration else None
    await session.commit()


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[User, str]:
    normalized = email.strip().lower()
    now = datetime.now(UTC)
    user = await session.scalar(select(User).where(User.email == normalized))
    if user is None:
        verify_password(password, dummy_password_hash())
        raise AuthError(GENERIC_LOGIN_ERROR)

    if user.locked_until is not None and user.locked_until > now:
        # Spend the same kind of work as a normal check, then keep the lock.
        verify_password(password, user.password_hash)
        await _record_failure(session, user)
        raise AuthError(GENERIC_LOGIN_ERROR)

    if not verify_password(password, user.password_hash):
        await _record_failure(session, user)
        raise AuthError(GENERIC_LOGIN_ERROR)

    if user.status != "approved":
        # DECISION: the status is shown only after the password checks out.
        # A wrong password still gets the generic error, so login does not
        # reveal that the email is registered.
        raise AuthError(STATUS_LOGIN_MESSAGES[user.status], status_code=403)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await revoke_user_sessions(session, user.id)
    raw = new_token()
    ttl = timedelta(hours=get_settings().session_ttl_hours)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + ttl,
            ip=ip,
            user_agent=user_agent,
        )
    )
    await write_audit(
        session,
        actor_user_id=user.id,
        action="auth.login",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
    )
    await session.commit()
    return user, raw


async def revoke_user_sessions(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    except_token_hash: str | None = None,
) -> None:
    now = datetime.now(UTC)
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if except_token_hash is not None:
        stmt = stmt.where(UserSession.token_hash != except_token_hash)
    await session.execute(stmt)


async def revoke_session(session: AsyncSession, raw_token: str | None, ip: str | None) -> None:
    if not raw_token:
        return
    now = datetime.now(UTC)
    row = await session.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(raw_token))
    )
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = now
    await write_audit(
        session,
        actor_user_id=row.user_id,
        action="auth.logout",
        target_type="user",
        target_id=str(row.user_id),
        ip=ip,
    )
    await session.commit()
