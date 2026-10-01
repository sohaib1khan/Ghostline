"""First-run admin creation. A database lock stops two setups from both winning."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import INSECURE_SECRET_VALUES, get_settings
from app.models.user import User
from app.security.passwords import hash_password, validate_password
from app.security.roles import STAFF_ROLES, SUPER_ADMIN_ROLE
from app.security.tokens import hash_token, new_token, token_matches
from app.services.audit import write_audit
from app.services.seed import seed_starter_content
from app.services.settings_store import delete_setting, get_setting, set_setting

SETUP_TOKEN_KEY = "setup_token_hash"
SETUP_COMPLETED_KEY = "setup_completed"
# Arbitrary constant. pg_advisory_xact_lock takes a bigint.
SETUP_LOCK_ID = 4815162342


class SetupError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def admin_exists(session: AsyncSession) -> bool:
    admin_id = await session.scalar(select(User.id).where(User.role.in_(STAFF_ROLES)).limit(1))
    return admin_id is not None


async def maybe_bootstrap_admin(session: AsyncSession) -> bool:
    """Create the first super admin from env when explicitly allowed.

    Returns True when a staff account now exists and the interactive setup token
    should not be printed. Raises RuntimeError if bootstrap is enabled but
    misconfigured, so a bad deploy fails closed instead of falling back.
    """
    settings = get_settings()
    if await admin_exists(session):
        return True
    if not settings.bootstrap_allow:
        return False

    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password
    first_name = settings.bootstrap_admin_first_name.strip() or "Admin"
    last_name = settings.bootstrap_admin_last_name.strip() or "User"
    if not email or not password:
        raise RuntimeError(
            "BOOTSTRAP_ALLOW is true but BOOTSTRAP_ADMIN_EMAIL / "
            "BOOTSTRAP_ADMIN_PASSWORD are missing"
        )
    if password.strip().lower() in INSECURE_SECRET_VALUES:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD is too weak or still an example value")
    try:
        validate_password(password, email)
    except ValueError as exc:
        raise RuntimeError(f"BOOTSTRAP_ADMIN_PASSWORD rejected: {exc}") from exc

    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": SETUP_LOCK_ID},
        )
        if await admin_exists(session):
            return True
        user = User(
            email=email,
            first_name=first_name[:80],
            last_name=last_name[:80],
            password_hash=hash_password(password),
            role=SUPER_ADMIN_ROLE,
            status="approved",
            failed_login_count=0,
        )
        session.add(user)
        await session.flush()
        await delete_setting(session, SETUP_TOKEN_KEY)
        await set_setting(session, SETUP_COMPLETED_KEY, True, is_secret=False)
        await write_audit(
            session,
            actor_user_id=user.id,
            action="setup.bootstrap",
            target_type="user",
            target_id=str(user.id),
            details={"email": email, "source": "env", "role": SUPER_ADMIN_ROLE},
            ip=None,
        )
    await seed_starter_content(session)
    # Never log the password. Confirm email only so operators can verify.
    print(f"GHOSTLINE BOOTSTRAP: super admin ready for {email}", flush=True)
    print(
        "GHOSTLINE BOOTSTRAP: clear BOOTSTRAP_ALLOW and the bootstrap password from .env",
        flush=True,
    )
    return True


async def ensure_setup_token(session: AsyncSession) -> str | None:
    """Print a fresh setup token when no admin exists. Returns the raw token."""
    if await admin_exists(session):
        return None
    token = new_token()
    await set_setting(session, SETUP_TOKEN_KEY, hash_token(token), is_secret=False)
    await session.commit()
    # docker compose logs backend  — this line is the one-time token.
    print(f"GHOSTLINE SETUP TOKEN: {token}", flush=True)
    return token


async def create_initial_admin(
    session: AsyncSession,
    *,
    setup_token: str,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    ip: str | None,
) -> User:
    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": SETUP_LOCK_ID},
        )
        if await admin_exists(session):
            raise SetupError(409, "Setup is already complete")
        stored = await get_setting(session, SETUP_TOKEN_KEY)
        if not isinstance(stored, str) or not token_matches(setup_token, stored):
            raise SetupError(403, "Invalid setup token")
        try:
            validate_password(password, email)
        except ValueError as exc:
            raise SetupError(400, str(exc)) from exc
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=hash_password(password),
            role=SUPER_ADMIN_ROLE,
            status="approved",
            failed_login_count=0,
        )
        session.add(user)
        await session.flush()
        await delete_setting(session, SETUP_TOKEN_KEY)
        await set_setting(session, SETUP_COMPLETED_KEY, True, is_secret=False)
        await write_audit(
            session,
            actor_user_id=user.id,
            action="setup.complete",
            target_type="user",
            target_id=str(user.id),
            details={"email": email},
            ip=ip,
        )
    # Seed commits on its own. Doing it inside begin() would close the setup
    # transaction before the admin row is committed.
    await seed_starter_content(session)
    return user
