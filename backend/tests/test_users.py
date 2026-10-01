"""Signup, approval, track access, and admin permission checks."""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.models.audit import AuditLog
from app.models.session import UserSession
from app.models.user import User
from app.security.rate_limit import limiter
from app.security.tokens import hash_token, new_token
from app.services.auth import GENERIC_LOGIN_ERROR, REJECTED_LOGIN_MESSAGE
from app.services.setup import ensure_setup_token
from app.services.signup import SIGNUP_MESSAGE
from app.services.tracks import ensure_tracks
from app.services.users import UserAdminError, update_user
from sqlalchemy import func, select, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
LEARNER_EMAIL = "grace@example.com"
PASSWORD = "correct-horse-battery"
OTHER_PASSWORD = "river-stone-lantern"
SAMPLE_ID = "00000000-0000-4000-8000-000000000001"

PROTECTED = [
    ("GET", "/api/me", None),
    ("PATCH", "/api/me", {"first_name": "Grace", "last_name": "Hopper"}),
    ("POST", "/api/me/password", {"current_password": PASSWORD, "new_password": OTHER_PASSWORD}),
    ("GET", "/api/learn/tracks", None),
    ("GET", "/api/learn/tracks/bash", None),
    ("GET", "/api/admin/users", None),
    (
        "POST",
        "/api/admin/users",
        {
            "first_name": "Should",
            "last_name": "Not",
            "email": "should-not-exist@example.com",
            "password": OTHER_PASSWORD,
            "role": "learner",
            "track_slugs": ["bash"],
        },
    ),
    ("PATCH", f"/api/admin/users/{SAMPLE_ID}", {"status": "disabled"}),
    ("POST", f"/api/admin/users/{SAMPLE_ID}/approve", {"track_slugs": ["bash"]}),
    ("POST", f"/api/admin/users/{SAMPLE_ID}/reject", None),
    ("PUT", f"/api/admin/users/{SAMPLE_ID}/tracks", {"track_slugs": ["bash"]}),
    (
        "POST",
        f"/api/admin/users/{SAMPLE_ID}/reset-password",
        {"password": OTHER_PASSWORD},
    ),
    ("POST", f"/api/admin/users/{SAMPLE_ID}/revoke-sessions", None),
    ("DELETE", f"/api/admin/users/{SAMPLE_ID}", None),
    ("GET", "/api/admin/notifications/channels", None),
    (
        "POST",
        "/api/admin/notifications/channels",
        {
            "name": "Ops",
            "provider": "webhook",
            "events": ["user.signup"],
            "is_enabled": False,
            "config": {"url": "https://example.com/hook"},
        },
    ),
    (
        "PUT",
        f"/api/admin/notifications/channels/{SAMPLE_ID}",
        {
            "name": "Ops",
            "provider": "webhook",
            "events": ["user.signup"],
            "is_enabled": False,
            "config": {"url": "https://example.com/hook"},
        },
    ),
    ("DELETE", f"/api/admin/notifications/channels/{SAMPLE_ID}", None),
    ("POST", f"/api/admin/notifications/channels/{SAMPLE_ID}/test", None),
    ("GET", "/api/admin/content/tree", None),
    ("PATCH", f"/api/admin/tracks/{SAMPLE_ID}", {"name": "Bash"}),
    ("POST", "/api/admin/modules", {"track_id": SAMPLE_ID, "title": "Intro"}),
    ("PATCH", f"/api/admin/modules/{SAMPLE_ID}", {"title": "Intro"}),
    ("DELETE", f"/api/admin/modules/{SAMPLE_ID}", None),
    ("POST", "/api/admin/lessons", {"module_id": SAMPLE_ID, "title": "Hello"}),
    ("GET", f"/api/admin/lessons/{SAMPLE_ID}", None),
    ("GET", f"/api/admin/lessons/{SAMPLE_ID}/preview", None),
    ("PATCH", f"/api/admin/lessons/{SAMPLE_ID}", {"title": "Hello"}),
    ("DELETE", f"/api/admin/lessons/{SAMPLE_ID}", None),
    ("POST", f"/api/admin/lessons/{SAMPLE_ID}/publish", None),
    (
        "POST",
        "/api/admin/exercises",
        {
            "lesson_id": SAMPLE_ID,
            "data": {
                "type": "recall",
                "prompt": "Print hello",
                "check": {"accepted_answers": ["print('hello')"]},
            },
        },
    ),
    (
        "PATCH",
        f"/api/admin/exercises/{SAMPLE_ID}",
        {
            "data": {
                "type": "recall",
                "prompt": "Print hello",
                "check": {"accepted_answers": ["print('hello')"]},
            }
        },
    ),
    ("DELETE", f"/api/admin/exercises/{SAMPLE_ID}", None),
    (
        "POST",
        "/api/admin/reorder",
        {"kind": "module", "parent_id": SAMPLE_ID, "ids": [SAMPLE_ID]},
    ),
    (
        "POST",
        "/api/admin/exercises/test-check",
        {
            "attempt": "ls",
            "data": {
                "type": "recall",
                "prompt": "List files",
                "check": {"accepted_answers": ["ls"]},
            },
        },
    ),
    ("GET", "/api/admin/export?track=bash", None),
    ("POST", "/api/admin/import", {"document": "slug: bash\nmodules: []\n", "dry_run": True}),
    (
        "POST",
        "/api/admin/content/parse-exercise",
        {
            "text": '{"type":"recall","prompt":"List","check":{"accepted_answers":["ls"]}}',
            "format": "json",
        },
    ),
    ("GET", f"/api/learn/lessons/{SAMPLE_ID}", None),
    ("GET", "/api/learn/tracks/bash/outline", None),
    ("GET", "/api/learn/dashboard", None),
    ("POST", f"/api/check/{SAMPLE_ID}", {"attempt": "ls"}),
    ("GET", "/api/me/stats", None),
    ("GET", "/api/games/catalog", None),
    ("GET", "/api/games/next?game=speed_drill", None),
    ("POST", f"/api/games/score/{SAMPLE_ID}", {"game": "speed_drill", "attempt": "ls"}),
    ("GET", "/api/games/leaderboard", None),
    ("GET", "/api/admin/settings", None),
    ("PUT", "/api/admin/settings", {"leaderboard_enabled": False}),
    ("GET", "/api/admin/ai/settings", None),
    (
        "PUT",
        "/api/admin/ai/settings",
        {
            "provider": "ollama",
            "model": "llama3.2",
            "base_url": "http://127.0.0.1:11434",
            "enabled": False,
        },
    ),
    ("POST", "/api/admin/ai/test", None),
    (
        "POST",
        "/api/admin/ai/draft-lesson",
        {
            "module_id": SAMPLE_ID,
            "topic": "lists",
            "difficulty": "beginner",
            "exercise_count": 1,
            "exercise_types": ["recall"],
        },
    ),
]

ADMIN_ONLY = [item for item in PROTECTED if item[1].startswith("/api/admin/")]


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
        await ensure_tracks(session)
    yield


@asynccontextmanager
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    if "ghostline_csrf" not in client.cookies:
        await client.get("/api/setup/status")
    return {"X-CSRF-Token": client.cookies["ghostline_csrf"]}


async def request(client: httpx.AsyncClient, method: str, path: str, body: dict | None):
    headers = await csrf_headers(client)
    return await client.request(method, path, headers=headers, json=body)


async def create_admin(client: httpx.AsyncClient) -> None:
    async with get_sessionmaker()() as session:
        token = await ensure_setup_token(session)
    response = await request(
        client,
        "POST",
        "/api/setup",
        {
            "setup_token": token,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": ADMIN_EMAIL,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    logged_in = await request(
        client,
        "POST",
        "/api/auth/login",
        {"email": ADMIN_EMAIL, "password": PASSWORD},
    )
    assert logged_in.status_code == 200


async def signup(client: httpx.AsyncClient, email: str, password: str = PASSWORD):
    return await request(
        client,
        "POST",
        "/api/auth/signup",
        {
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": email,
            "password": password,
        },
    )


async def user_count(email: str) -> int:
    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.email == email)
        )
    return int(count or 0)


async def test_signup_before_setup_is_refused(database) -> None:
    async with api_client() as client:
        response = await signup(client, LEARNER_EMAIL)
    assert response.status_code == 409
    assert await user_count(LEARNER_EMAIL) == 0


async def test_signup_auto_approves_and_hides_duplicate_emails(database) -> None:
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        first = await signup(guest, "Grace@Example.com")
        second = await signup(guest, LEARNER_EMAIL, OTHER_PASSWORD)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() == {"message": SIGNUP_MESSAGE}
    assert await user_count(LEARNER_EMAIL) == 1

    async with get_sessionmaker()() as session:
        row = await session.scalar(select(User).where(User.email == LEARNER_EMAIL))
        assert row is not None
        assert row.status == "approved"
        assert row.role == "learner"

    async with api_client() as guest:
        wrong = await request(
            guest,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": "not-the-password"},
        )
        signed_in = await request(
            guest,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        replaced = await request(
            guest,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": OTHER_PASSWORD},
        )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == GENERIC_LOGIN_ERROR
    assert signed_in.status_code == 200
    assert "ghostline_session" in signed_in.cookies
    assert replaced.status_code == 401
    assert replaced.json()["detail"] == GENERIC_LOGIN_ERROR


async def test_approval_limits_visible_tracks(database) -> None:
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        created = await signup(guest, LEARNER_EMAIL)
        assert created.status_code == 201
        async with get_sessionmaker()() as session:
            learner = await session.scalar(select(User).where(User.email == LEARNER_EMAIL))
            assert learner is not None
            learner_id = learner.id
        unknown = await request(
            admin,
            "POST",
            f"/api/admin/users/{learner_id}/approve",
            {"track_slugs": ["cobol"]},
        )
        assert unknown.status_code == 400
        approved = await request(
            admin,
            "POST",
            f"/api/admin/users/{learner_id}/approve",
            {"track_slugs": ["python"]},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["track_slugs"] == ["python"]
        admin_tracks = await request(admin, "GET", "/api/learn/tracks", None)
        bash = await request(admin, "GET", "/api/learn/tracks/bash", None)

    assert [track["slug"] for track in admin_tracks.json()] == [
        "bash",
        "python",
        "go",
        "javascript",
        "sql",
    ]
    assert bash.status_code == 200

    async with api_client() as learner:
        logged_in = await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        assert logged_in.status_code == 200
        visible = await request(learner, "GET", "/api/learn/tracks", None)
        allowed = await request(learner, "GET", "/api/learn/tracks/python", None)
        blocked = await request(learner, "GET", "/api/learn/tracks/bash", None)
        missing = await request(learner, "GET", "/api/learn/tracks/missing", None)
        admin_page = await request(learner, "GET", "/api/admin/users", None)
    assert [track["slug"] for track in visible.json()] == ["python"]
    assert allowed.status_code == 200
    assert blocked.status_code == 403
    assert missing.status_code == 404
    assert admin_page.status_code == 403

    async with get_sessionmaker()() as session:
        audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.approve"))
        assert audit is not None
        assert "password" not in audit.details


async def test_anonymous_and_learner_are_stopped_on_protected_routes(database) -> None:
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        assert (await signup(guest, LEARNER_EMAIL)).status_code == 201
        async with get_sessionmaker()() as session:
            learner = await session.scalar(select(User).where(User.email == LEARNER_EMAIL))
            assert learner is not None
            learner_id = str(learner.id)
        await request(
            admin,
            "POST",
            f"/api/admin/users/{learner_id}/approve",
            {"track_slugs": ["bash"]},
        )

    async with api_client() as anon:
        for method, path, body in PROTECTED:
            response = await request(anon, method, path, body)
            assert response.status_code == 401, path

    async with api_client() as learner:
        await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        me = await request(learner, "GET", "/api/me", None)
        assert me.status_code == 200
        for method, path, body in ADMIN_ONLY:
            response = await request(learner, method, path, body)
            assert response.status_code == 403, path
    assert await user_count("should-not-exist@example.com") == 0


async def test_direct_create_reset_reject_and_last_admin(database) -> None:
    async with api_client() as admin, api_client() as learner:
        await create_admin(admin)
        created = await request(
            admin,
            "POST",
            "/api/admin/users",
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": LEARNER_EMAIL,
                "password": PASSWORD,
                "role": "learner",
                "track_slugs": ["go"],
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "approved"
        learner_id = created.json()["id"]
        logged_in = await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        assert logged_in.status_code == 200
        session_cookie = learner.cookies["ghostline_session"]

        reset = await request(
            admin,
            "POST",
            f"/api/admin/users/{learner_id}/reset-password",
            {"password": OTHER_PASSWORD},
        )
        assert reset.status_code == 204
        stale = await learner.get("/api/me")
        assert stale.status_code == 401
        again = await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": OTHER_PASSWORD},
        )
        assert again.status_code == 200
        assert learner.cookies["ghostline_session"] != session_cookie

        rejected = await request(admin, "POST", f"/api/admin/users/{learner_id}/reject", None)
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["track_slugs"] == []
        blocked = await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": OTHER_PASSWORD},
        )
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == REJECTED_LOGIN_MESSAGE

        async with get_sessionmaker()() as session:
            admin_row = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
            assert admin_row is not None
            admin_id = admin_row.id
        demoted = await request(
            admin,
            "PATCH",
            f"/api/admin/users/{admin_id}",
            {"status": "disabled"},
        )
        assert demoted.status_code == 409
        assert demoted.json()["detail"] == "You cannot change your own access"

        async with get_sessionmaker()() as lookup:
            actor = await lookup.scalar(select(User).where(User.email == LEARNER_EMAIL))
            target = await lookup.scalar(select(User).where(User.email == ADMIN_EMAIL))
            assert actor is not None and target is not None
            target_id = target.id
        async with get_sessionmaker()() as session:
            with pytest.raises(UserAdminError) as caught:
                await update_user(
                    session,
                    actor=actor,
                    user_id=target_id,
                    role=None,
                    status="disabled",
                    ip=None,
                )
        assert caught.value.status_code == 409
        assert caught.value.detail == "The last super admin cannot be removed"


async def test_profile_keeps_this_session_and_revokes_others(database) -> None:
    async with api_client() as client:
        await create_admin(client)
        renamed = await request(
            client,
            "PATCH",
            "/api/me",
            {"first_name": "Augusta", "last_name": "King"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["first_name"] == "Augusta"

        async with get_sessionmaker()() as session:
            admin = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
            assert admin is not None
            extra = new_token()
            session.add(
                UserSession(
                    user_id=admin.id,
                    token_hash=hash_token(extra),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            await session.commit()

        changed = await request(
            client,
            "POST",
            "/api/me/password",
            {"current_password": PASSWORD, "new_password": OTHER_PASSWORD},
        )
        assert changed.status_code == 204
        still = await request(client, "GET", "/api/me", None)
        assert still.status_code == 200

        async with get_sessionmaker()() as session:
            row = await session.scalar(
                select(UserSession).where(UserSession.token_hash == hash_token(extra))
            )
            assert row is not None
            assert row.revoked_at is not None


async def test_signup_rate_limit(database) -> None:
    limiter.enabled = True
    limiter.reset()
    try:
        async with api_client() as admin, api_client() as guest:
            await create_admin(admin)
            codes = []
            for index in range(4):
                response = await signup(guest, f"person{index}@example.com")
                codes.append(response.status_code)
        assert codes[:3] == [201, 201, 201]
        assert codes[3] == 429
    finally:
        limiter.enabled = False
        limiter.reset()
