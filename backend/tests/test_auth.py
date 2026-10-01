"""Setup, sessions, lockout, and CSRF against Postgres."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.models.session import UserSession
from app.models.user import User
from app.security.rate_limit import limiter
from app.security.tokens import hash_token, token_matches
from app.services.auth import GENERIC_LOGIN_ERROR
from app.services.settings_store import get_setting
from app.services.setup import SETUP_TOKEN_KEY, ensure_setup_token
from sqlalchemy import select, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"
NAME = {"first_name": "Ada", "last_name": "Lovelace"}


@pytest.fixture
async def database():
    async with get_sessionmaker()() as session:
        await session.execute(
            text(
                "TRUNCATE audit_log, sessions, app_settings, users, notification_channels, "
                "practice_events, exercise_progress, user_stats, exercises, lessons, modules, "
                "content_revisions RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    if "ghostline_csrf" not in client.cookies:
        await client.get("/api/setup/status")
    return {"X-CSRF-Token": client.cookies["ghostline_csrf"]}


def setup_body(token: str, **overrides) -> dict:
    body = {
        "setup_token": token,
        "email": EMAIL,
        "password": PASSWORD,
        **NAME,
    }
    body.update(overrides)
    return body


async def test_setup_rejects_a_bad_token(database, client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        await ensure_setup_token(session)
    response = await client.post(
        "/api/setup",
        json=setup_body("this-token-is-not-the-real-one"),
        headers=await csrf_headers(client),
    )
    assert response.status_code == 403
    async with get_sessionmaker()() as session:
        assert await session.scalar(select(User.id)) is None


async def test_setup_stores_only_the_token_hash(database) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)
        stored = await get_setting(session, SETUP_TOKEN_KEY)
    assert token
    assert stored != token
    assert token_matches(token, stored)


async def test_setup_then_second_attempt_conflicts(database, client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)
    headers = await csrf_headers(client)
    created = await client.post("/api/setup", json=setup_body(token), headers=headers)
    assert created.status_code == 201
    assert created.json()["role"] == "super_admin"
    assert created.json()["status"] == "approved"
    again = await client.post("/api/setup", json=setup_body(token), headers=headers)
    assert again.status_code == 409
    status = await client.get("/api/setup/status")
    assert status.json() == {"setup_required": False}


async def test_replaced_setup_token_stops_working(database, client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        first = await ensure_setup_token(session)
        second = await ensure_setup_token(session)
    headers = await csrf_headers(client)
    stale = await client.post("/api/setup", json=setup_body(first), headers=headers)
    assert stale.status_code == 403
    fresh = await client.post("/api/setup", json=setup_body(second), headers=headers)
    assert fresh.status_code == 201


async def test_common_password_is_rejected_at_setup(database, client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)
    response = await client.post(
        "/api/setup",
        json=setup_body(token, password="password1234"),
        headers=await csrf_headers(client),
    )
    assert response.status_code == 400
    assert "common" in response.json()["detail"]


async def test_concurrent_setup_allows_one_admin(database) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)

    async def submit(email: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            await http.get("/api/setup/status")
            return await http.post(
                "/api/setup",
                json=setup_body(token, email=email),
                headers={"X-CSRF-Token": http.cookies["ghostline_csrf"]},
            )

    first, second = await asyncio.gather(
        submit("one@example.com"),
        submit("two@example.com"),
    )
    codes = sorted([first.status_code, second.status_code])
    assert codes == [201, 409]
    async with get_sessionmaker()() as session:
        admins = (await session.scalars(select(User).where(User.role == "super_admin"))).all()
    assert len(admins) == 1


async def test_bootstrap_creates_admin_once(database, monkeypatch) -> None:
    from app.config import get_settings
    from app.services.setup import maybe_bootstrap_admin

    monkeypatch.setenv("BOOTSTRAP_ALLOW", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "boot@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "correct-horse-battery")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_FIRST_NAME", "Boot")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_LAST_NAME", "Strap")
    get_settings.cache_clear()
    async with get_sessionmaker()() as session:
        assert await maybe_bootstrap_admin(session) is True
        assert await maybe_bootstrap_admin(session) is True
        admins = (await session.scalars(select(User).where(User.role == "super_admin"))).all()
    assert len(admins) == 1
    assert admins[0].email == "boot@example.com"
    get_settings.cache_clear()


async def test_bootstrap_refuses_weak_password(database, monkeypatch) -> None:
    from app.config import get_settings
    from app.services.setup import maybe_bootstrap_admin

    monkeypatch.setenv("BOOTSTRAP_ALLOW", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "boot@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "change-me")
    get_settings.cache_clear()
    async with get_sessionmaker()() as session:
        with pytest.raises(RuntimeError, match="weak|example"):
            await maybe_bootstrap_admin(session)
        assert await session.scalar(select(User.id)) is None
    get_settings.cache_clear()


async def test_bootstrap_off_does_nothing(database, monkeypatch) -> None:
    from app.config import get_settings
    from app.services.setup import maybe_bootstrap_admin

    monkeypatch.setenv("BOOTSTRAP_ALLOW", "false")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    async with get_sessionmaker()() as session:
        assert await maybe_bootstrap_admin(session) is False
        assert await session.scalar(select(User.id)) is None
    get_settings.cache_clear()


async def _create_admin(client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)
    created = await client.post(
        "/api/setup",
        json=setup_body(token),
        headers=await csrf_headers(client),
    )
    assert created.status_code == 201


async def test_login_logout_and_session_cookie(database, client: httpx.AsyncClient) -> None:
    await _create_admin(client)
    headers = await csrf_headers(client)
    logged_in = await client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=headers,
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["email"] == EMAIL
    cookie = logged_in.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookie if item.startswith("ghostline_session="))
    attributes = [part.strip().lower() for part in session_cookie.split(";")]
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert "secure" not in attributes

    raw = client.cookies["ghostline_session"]
    async with get_sessionmaker()() as session:
        row = await session.scalar(select(UserSession))
    assert row is not None
    assert row.token_hash == hash_token(raw)
    assert row.token_hash != raw

    me = await client.get("/api/me")
    assert me.status_code == 200
    logged_out = await client.post("/api/auth/logout", headers=headers)
    assert logged_out.status_code == 204
    after = await client.get("/api/me")
    assert after.status_code == 401


async def test_unknown_email_and_bad_password_match(database, client: httpx.AsyncClient) -> None:
    await _create_admin(client)
    headers = await csrf_headers(client)
    unknown = await client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": PASSWORD},
        headers=headers,
    )
    wrong = await client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": "not-the-right-secret"},
        headers=headers,
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"] == GENERIC_LOGIN_ERROR


async def test_lockout_blocks_the_correct_password(database, client: httpx.AsyncClient) -> None:
    await _create_admin(client)
    headers = await csrf_headers(client)
    for _ in range(5):
        failed = await client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "not-the-right-secret"},
            headers=headers,
        )
        assert failed.status_code == 401
        assert failed.json()["detail"] == GENERIC_LOGIN_ERROR
    blocked = await client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=headers,
    )
    assert blocked.status_code == 401
    assert blocked.json()["detail"] == GENERIC_LOGIN_ERROR

    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.email == EMAIL))
        assert user is not None
        assert user.locked_until is not None
        user.locked_until = datetime.now(UTC) - timedelta(seconds=5)
        user.failed_login_count = 0
        await session.commit()

    restored = await client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=headers,
    )
    assert restored.status_code == 200


async def test_mutating_request_without_csrf_is_rejected(
    database, client: httpx.AsyncClient
) -> None:
    await _create_admin(client)
    response = await client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


async def test_login_rate_limit(database, client: httpx.AsyncClient) -> None:
    await _create_admin(client)
    headers = await csrf_headers(client)
    limiter.enabled = True
    limiter.reset()
    statuses = []
    for _ in range(6):
        response = await client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "not-the-right-secret"},
            headers=headers,
        )
        statuses.append(response.status_code)
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429
