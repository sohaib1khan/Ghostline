"""Name and password changes for the signed-in account."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.passwords import hash_password, validate_password, verify_password
from app.security.tokens import hash_token
from app.services.audit import write_audit
from app.services.auth import revoke_user_sessions


class ProfileError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def update_profile(
    session: AsyncSession,
    user: User,
    *,
    first_name: str,
    last_name: str,
    ip: str | None,
) -> User:
    user.first_name = first_name
    user.last_name = last_name
    await write_audit(
        session,
        actor_user_id=user.id,
        action="profile.update",
        target_type="user",
        target_id=str(user.id),
        details={"first_name": first_name, "last_name": last_name},
        ip=ip,
    )
    await session.commit()
    return user


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
    raw_token: str | None,
    ip: str | None,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise ProfileError(400, "Current password is incorrect")
    try:
        validate_password(new_password, user.email)
    except ValueError as exc:
        raise ProfileError(400, str(exc)) from exc
    if verify_password(new_password, user.password_hash):
        raise ProfileError(400, "Choose a different password")
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    # DECISION: other devices are signed out. This browser keeps its session.
    except_hash = hash_token(raw_token) if raw_token else None
    await revoke_user_sessions(session, user.id, except_token_hash=except_hash)
    await write_audit(
        session,
        actor_user_id=user.id,
        action="profile.password",
        target_type="user",
        target_id=str(user.id),
        details={},
        ip=ip,
    )
    await session.commit()
