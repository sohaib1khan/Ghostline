"""Notification channels: encrypted config, fan-out, and provider requests."""

import json
import os
from contextlib import asynccontextmanager

import httpx
import pytest
from app.config import get_settings
from app.db import get_sessionmaker
from app.main import app
from app.models.audit import AuditLog
from app.models.notification import NotificationChannel
from app.models.user import User
from app.services.notifications.base import DeliveryError, Outbound
from app.services.notifications.dispatcher import flush_notifications
from app.services.notifications.registry import SENDERS
from app.services.setup import ensure_setup_token
from app.services.signup import SIGNUP_MESSAGE
from app.services.tracks import ensure_tracks
from cryptography.fernet import Fernet
from sqlalchemy import select, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
LEARNER_EMAIL = "grace@example.com"
PASSWORD = "correct-horse-battery"
SECRET = "super-secret-value"
SLACK_URL = f"https://hooks.slack.com/services/T00/B00/{SECRET}"


@pytest.fixture
async def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("APP_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield key
    await flush_notifications()
    get_settings.cache_clear()


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
    created = await request(
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
    assert created.status_code == 201
    logged_in = await request(
        client,
        "POST",
        "/api/auth/login",
        {"email": ADMIN_EMAIL, "password": PASSWORD},
    )
    assert logged_in.status_code == 200


def record_posts(monkeypatch):
    calls: list[dict] = []

    async def fake(url, **kwargs):
        calls.append({"url": url, **kwargs})

    monkeypatch.setattr("app.services.notifications.http.post_json", fake)
    return calls


async def test_secrets_stay_hidden_and_blank_updates_keep_them(
    database, encryption_key, monkeypatch
) -> None:
    calls = record_posts(monkeypatch)
    async with api_client() as admin:
        await create_admin(admin)
        created = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Ops",
                "provider": "slack",
                "events": ["user.signup"],
                "config": {"webhook_url": SLACK_URL},
            },
        )
        assert created.status_code == 201
        body = created.json()
        channel_id = body["id"]
        assert SECRET not in created.text
        assert body["secrets"] == {"webhook_url": True}
        assert body["config"] == {}

        listed = await request(admin, "GET", "/api/admin/notifications/channels", None)
        assert SECRET not in listed.text
        assert listed.json()["email_channel_ready"] is False

        updated = await request(
            admin,
            "PUT",
            f"/api/admin/notifications/channels/{channel_id}",
            {
                "name": "Ops",
                "provider": "slack",
                "events": ["user.signup"],
                "config": {"webhook_url": ""},
            },
        )
        assert updated.status_code == 200
        assert SECRET not in updated.text
        tested = await request(
            admin, "POST", f"/api/admin/notifications/channels/{channel_id}/test", None
        )
        assert tested.status_code == 200
        assert tested.json()["ok"] is True

    assert calls[0]["url"] == SLACK_URL
    async with get_sessionmaker()() as session:
        row = await session.scalar(select(NotificationChannel))
        assert row is not None
        assert SECRET not in row.config_encrypted
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.action == "notification.create")
        )
        assert audit is not None
        assert "webhook_url" not in audit.details


async def test_failing_channel_does_not_break_signup(database, encryption_key, monkeypatch) -> None:
    async def fail(url, **kwargs):
        del url, kwargs
        raise DeliveryError("The service returned HTTP 401")

    monkeypatch.setattr("app.services.notifications.http.post_json", fail)
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        created = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Ops",
                "provider": "slack",
                "events": ["user.signup"],
                "config": {"webhook_url": SLACK_URL},
            },
        )
        assert created.status_code == 201
        signed = await request(
            guest,
            "POST",
            "/api/auth/signup",
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": LEARNER_EMAIL,
                "password": PASSWORD,
            },
        )
    assert signed.status_code == 201
    assert signed.json() == {"message": SIGNUP_MESSAGE}
    await flush_notifications()
    async with get_sessionmaker()() as session:
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.action == "notification.delivery_failed")
        )
        assert audit is not None
        assert audit.details["error"] == "The service returned HTTP 401"
        assert SECRET not in json.dumps(audit.details)
        user = await session.scalar(select(User).where(User.email == LEARNER_EMAIL))
        assert user is not None
        assert user.status == "pending"


async def test_approval_email_goes_to_the_learner(database, encryption_key, monkeypatch) -> None:
    calls = record_posts(monkeypatch)
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        channel = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Mail",
                "provider": "resend",
                "events": ["user.approved"],
                "config": {
                    "api_key": SECRET,
                    "from_email": "ghostline@example.com",
                    "to_email": "ops@example.com",
                },
            },
        )
        assert channel.status_code == 201
        assert channel.json()["config"]["to_email"] == "ops@example.com"
        assert SECRET not in channel.text
        signed = await request(
            guest,
            "POST",
            "/api/auth/signup",
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": LEARNER_EMAIL,
                "password": PASSWORD,
            },
        )
        assert signed.status_code == 201
        async with get_sessionmaker()() as session:
            learner = await session.scalar(select(User).where(User.email == LEARNER_EMAIL))
            assert learner is not None
            learner_id = learner.id
        approved = await request(
            admin,
            "POST",
            f"/api/admin/users/{learner_id}/approve",
            {"track_slugs": ["python"]},
        )
        assert approved.status_code == 200
    await flush_notifications()
    assert calls
    sent = calls[0]["json"]
    assert sent["to"] == [LEARNER_EMAIL]
    assert sent["subject"] == "Your Ghostline access was approved"
    assert SECRET not in json.dumps(calls[0]["json"])
    assert calls[0]["headers"]["Authorization"] == f"Bearer {SECRET}"


async def test_disabled_and_unsubscribed_channels_stay_quiet(
    database, encryption_key, monkeypatch
) -> None:
    calls = record_posts(monkeypatch)
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        disabled = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Off",
                "provider": "webhook",
                "events": ["user.signup"],
                "is_enabled": False,
                "config": {"url": "https://example.com/off"},
            },
        )
        other = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Elsewhere",
                "provider": "webhook",
                "events": ["user.approved"],
                "config": {"url": "https://example.com/other"},
            },
        )
        assert disabled.status_code == other.status_code == 201
        signed = await request(
            guest,
            "POST",
            "/api/auth/signup",
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": LEARNER_EMAIL,
                "password": PASSWORD,
            },
        )
        assert signed.status_code == 201
    await flush_notifications()
    assert calls == []


async def test_send_test_records_failure(database, encryption_key, monkeypatch) -> None:
    async def fail(url, **kwargs):
        del url, kwargs
        raise DeliveryError("Could not reach the notification service")

    monkeypatch.setattr("app.services.notifications.http.post_json", fail)
    async with api_client() as admin:
        await create_admin(admin)
        created = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Hook",
                "provider": "webhook",
                "events": [],
                "config": {"url": "http://10.1.1.8/hook", "bearer_token": SECRET},
            },
        )
        assert created.status_code == 201
        assert SECRET not in created.text
        channel_id = created.json()["id"]
        tested = await request(
            admin, "POST", f"/api/admin/notifications/channels/{channel_id}/test", None
        )
        assert tested.status_code == 200
        assert tested.json()["ok"] is False
        listed = await request(admin, "GET", "/api/admin/notifications/channels", None)
        row = listed.json()["channels"][0]
        assert row["last_test_ok"] is False
        assert row["last_test_at"] is not None
        assert SECRET not in listed.text


async def test_url_with_userinfo_is_rejected(database, encryption_key) -> None:
    async with api_client() as admin:
        await create_admin(admin)
        rejected = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Hook",
                "provider": "webhook",
                "events": ["user.signup"],
                "config": {"url": "https://user:s3cr3t-token@example.com/hook"},
            },
        )
    assert rejected.status_code == 400
    assert "s3cr3t-token" not in rejected.text


async def test_admin_sign_in_notifies_subscribed_channels(
    database, encryption_key, monkeypatch
) -> None:
    calls = record_posts(monkeypatch)
    async with api_client() as admin:
        await create_admin(admin)
        await flush_notifications()
        calls.clear()
        created = await request(
            admin,
            "POST",
            "/api/admin/notifications/channels",
            {
                "name": "Sign-ins",
                "provider": "webhook",
                "events": ["admin.login"],
                "config": {"url": "https://example.com/admin"},
            },
        )
        assert created.status_code == 201
        logged_in = await request(
            admin,
            "POST",
            "/api/auth/login",
            {"email": ADMIN_EMAIL, "password": PASSWORD},
        )
        assert logged_in.status_code == 200
    await flush_notifications()
    assert len(calls) == 1
    assert calls[0]["json"]["event"] == "admin.login"
    assert calls[0]["json"]["body"] == f"{ADMIN_EMAIL} signed in."
    assert "ip" not in calls[0]["json"]


@pytest.mark.parametrize(
    ("provider", "config", "check"),
    [
        (
            "resend",
            {
                "api_key": SECRET,
                "from_email": "ghostline@example.com",
                "to_email": "ops@example.com",
            },
            "resend",
        ),
        (
            "gotify",
            {"base_url": "http://gotify.local", "token": SECRET, "priority": 5},
            "gotify",
        ),
        ("slack", {"webhook_url": SLACK_URL}, "slack"),
        ("discord", {"webhook_url": "https://discord.com/api/webhooks/1/secret"}, "discord"),
        (
            "ntfy",
            {"base_url": "http://ntfy.local", "topic": "ghostline", "token": SECRET},
            "ntfy",
        ),
        (
            "webhook",
            {"url": "https://example.com/hook", "bearer_token": SECRET},
            "webhook",
        ),
    ],
)
async def test_provider_builds_the_request(monkeypatch, provider, config, check) -> None:
    calls = record_posts(monkeypatch)
    message = Outbound(
        event="user.signup",
        title="New Ghostline signup",
        body="Ada Lovelace (ada@example.com) asked for access." + ("." * 3000),
        recipient="ada@example.com",
    )
    await SENDERS[provider](config, message)
    sent = calls[0]
    if check == "resend":
        assert sent["url"] == "https://api.resend.com/emails"
        assert sent["headers"]["Authorization"] == f"Bearer {SECRET}"
        assert sent["json"]["to"] == ["ada@example.com"]
    elif check == "gotify":
        assert sent["url"] == "http://gotify.local/message"
        assert sent["headers"]["X-Gotify-Key"] == SECRET
        assert "token" not in sent["url"]
        assert sent["json"]["priority"] == 5
    elif check == "slack":
        assert sent["url"] == SLACK_URL
        assert sent["json"]["text"].startswith("*New Ghostline signup*")
    elif check == "discord":
        assert len(sent["json"]["content"]) <= 2000
    elif check == "ntfy":
        assert sent["url"] == "http://ntfy.local/ghostline"
        assert sent["headers"]["Authorization"] == f"Bearer {SECRET}"
        assert sent["headers"]["Title"] == "New Ghostline signup"
    else:
        assert sent["url"] == "https://example.com/hook"
        assert sent["headers"]["Authorization"] == f"Bearer {SECRET}"
        assert sent["json"]["event"] == "user.signup"


async def test_smtp_uses_starttls(monkeypatch) -> None:
    sent: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def ehlo(self):
            return None

        def starttls(self):
            sent["starttls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, email):
            sent["to"] = email["To"]
            sent["subject"] = email["Subject"]

        def quit(self):
            return None

    monkeypatch.setattr("app.services.notifications.smtp.smtplib.SMTP", FakeSMTP)
    message = Outbound(
        event="notification.test",
        title="Ghostline test",
        body="This is a test message from Ghostline.",
        recipient="ops@example.com",
    )
    await SENDERS["smtp"](
        {
            "host": "mail.internal",
            "port": 587,
            "security": "starttls",
            "username": "ghostline",
            "password": SECRET,
            "from_email": "ghostline@example.com",
            "to_email": "ops@example.com",
        },
        message,
    )
    assert sent["host"] == "mail.internal"
    assert sent["port"] == 587
    assert sent["starttls"] is True
    assert sent["login"] == ("ghostline", SECRET)
    assert sent["to"] == "ops@example.com"
