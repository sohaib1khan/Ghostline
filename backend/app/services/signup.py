"""Public signup. The response does not reveal whether an email is taken."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.passwords import hash_password, validate_password
from app.services.audit import write_audit
from app.services.notifications.dispatcher import dispatch_event
from app.services.setup import admin_exists

SIGNUP_MESSAGE = "Thanks for signing up! An admin will reach out to you for access approval."


class SignupError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def signup(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    ip: str | None,
) -> str:
    if not await admin_exists(session):
        raise SignupError(409, "Setup is not complete")
    normalized = email.strip().lower()
    try:
        validate_password(password, normalized)
    except ValueError as exc:
        raise SignupError(400, str(exc)) from exc

    # DECISION: hash before the lookup so a taken email does not return faster
    # than a new account. A duplicate still creates nothing and uses the same message.
    password_hash = hash_password(password)
    existing = await session.scalar(select(User.id).where(User.email == normalized))
    if existing is not None:
        return SIGNUP_MESSAGE

    user = User(
        email=normalized,
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        role="learner",
        status="pending",
        failed_login_count=0,
    )
    session.add(user)
    await session.flush()
    await write_audit(
        session,
        actor_user_id=None,
        action="user.signup",
        target_type="user",
        target_id=str(user.id),
        details={"email": normalized},
        ip=ip,
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return SIGNUP_MESSAGE

    # Delivery runs after commit. A missing or failing channel must not undo the account.
    await dispatch_event(
        "user.signup",
        {"email": normalized, "first_name": first_name, "last_name": last_name},
    )
    return SIGNUP_MESSAGE
