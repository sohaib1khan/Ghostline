from datetime import timedelta

from app.config import Settings
from app.security.cookies import cookies_are_secure, csrf_cookie_kwargs, session_cookie_kwargs
from app.services.auth import LOCKOUT_MAX_SECONDS, lock_duration


def _settings(app_env: str) -> Settings:
    return Settings(
        app_env=app_env,
        app_secret_key="x" * 48,
        app_encryption_key="y" * 48,
        database_url="postgresql+asyncpg://ghostline:s3cret@db:5432/ghostline",
    )


def test_session_cookie_flags() -> None:
    development = session_cookie_kwargs(_settings("development"))
    production = session_cookie_kwargs(_settings("production"))
    assert development["httponly"] is True
    assert development["samesite"] == "lax"
    assert development["secure"] is False
    assert production["secure"] is True
    assert cookies_are_secure(_settings("production")) is True


def test_csrf_cookie_is_readable_by_script() -> None:
    kwargs = csrf_cookie_kwargs(_settings("development"))
    assert kwargs["httponly"] is False
    assert kwargs["samesite"] == "lax"


def test_lockout_backoff() -> None:
    assert lock_duration(4) is None
    assert lock_duration(5) == timedelta(seconds=30)
    assert lock_duration(6) == timedelta(seconds=60)
    assert lock_duration(30) == timedelta(seconds=LOCKOUT_MAX_SECONDS)
