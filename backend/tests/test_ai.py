"""AI settings stay secret, and a draft is saved only when the model output is valid."""

import json
import os
from contextlib import asynccontextmanager

import httpx
import pytest
from app.config import get_settings
from app.db import get_sessionmaker
from app.main import app
from app.models.audit import AuditLog
from app.models.content import Lesson
from app.models.setting import AppSetting
from app.services.setup import ensure_setup_token
from app.services.tracks import ensure_tracks
from cryptography.fernet import Fernet
from sqlalchemy import func, select, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"
API_KEY = "sk-phase8-test-key"

LESSON = {
    "title": "Print a greeting",
    "summary": "Send hello to the output.",
    "body_markdown": "The print function writes a line of text.",
    "exercises": [
        {
            "type": "recall",
            "prompt": "Print hello.",
            "check": {"mode": "answers", "accepted_answers": ['print("hello")']},
        }
    ],
}


@pytest.fixture
async def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("APP_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield key
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


async def request(client: httpx.AsyncClient, method: str, path: str, body: dict | None = None):
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
        client, "POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert logged_in.status_code == 200


def provider_body(text: str, url: str) -> dict:
    if "anthropic.com" in url:
        return {"content": [{"type": "text", "text": text}]}
    if "openai.com" in url:
        return {"choices": [{"message": {"content": text}}]}
    return {"message": {"content": text}}


async def lesson_count() -> int:
    async with get_sessionmaker()() as session:
        value = await session.scalar(select(func.count()).select_from(Lesson))
        return int(value or 0)


async def test_draft_is_saved_only_when_the_model_output_is_valid(
    database, encryption_key, monkeypatch
) -> None:
    del encryption_key
    calls: list[dict] = []
    mode = {"text": '{"ok": true}'}

    async def fake_post(url, *, headers, payload, timeout):
        del payload, timeout
        calls.append({"url": url, "headers": headers})
        return provider_body(mode["text"], url)

    monkeypatch.setattr("app.services.ai.transport.post_json", fake_post)

    async with api_client() as client:
        await create_admin(client)
        tree = await request(client, "GET", "/api/admin/content/tree")
        assert tree.status_code == 200
        module_id = tree.json()["tracks"][0]["modules"][0]["id"]
        before = await lesson_count()

        rejected = await request(
            client,
            "PUT",
            "/api/admin/ai/settings",
            {
                "provider": "ollama",
                "model": "llama3.2",
                "base_url": "http://169.254.169.254",
                "enabled": False,
            },
        )
        assert rejected.status_code == 422

        saved = await request(
            client,
            "PUT",
            "/api/admin/ai/settings",
            {
                "provider": "anthropic",
                "model": "claude-test",
                "max_tokens": 1024,
                "timeout_seconds": 15,
                "enabled": False,
                "api_key": API_KEY,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["api_key_set"] is True
        assert API_KEY not in saved.text
        visible = await request(client, "GET", "/api/admin/ai/settings")
        assert visible.status_code == 200
        assert visible.json()["provider"] == "anthropic"
        assert API_KEY not in visible.text
        async with get_sessionmaker()() as session:
            secret = await session.scalar(select(AppSetting).where(AppSetting.key == "ai_api_key"))
            assert secret is not None
            assert secret.is_secret is True
            assert API_KEY not in json.dumps(secret.value)

        tested = await request(client, "POST", "/api/admin/ai/test")
        assert tested.status_code == 200
        assert calls[-1]["url"].startswith("https://api.anthropic.com/")
        assert calls[-1]["headers"]["x-api-key"] == API_KEY

        switched = await request(
            client,
            "PUT",
            "/api/admin/ai/settings",
            {"provider": "openai", "model": "gpt-test", "enabled": False},
        )
        assert switched.status_code == 200
        assert switched.json()["provider"] == "openai"
        assert switched.json()["api_key_set"] is True
        await request(client, "POST", "/api/admin/ai/test")
        assert calls[-1]["url"].startswith("https://api.openai.com/")
        assert calls[-1]["headers"]["authorization"] == f"Bearer {API_KEY}"

        ollama = await request(
            client,
            "PUT",
            "/api/admin/ai/settings",
            {
                "provider": "ollama",
                "model": "llama3.2",
                "base_url": "http://127.0.0.1:11434",
                "enabled": True,
                "clear_api_key": True,
            },
        )
        assert ollama.status_code == 200
        assert ollama.json()["api_key_set"] is False
        await request(client, "POST", "/api/admin/ai/test")
        assert calls[-1]["url"] == "http://127.0.0.1:11434/api/chat"
        assert "authorization" not in calls[-1]["headers"]

        mode["text"] = "```json\n" + json.dumps(LESSON) + "\n```"
        drafted = await request(
            client,
            "POST",
            "/api/admin/ai/draft-lesson",
            {
                "module_id": module_id,
                "topic": "printing",
                "difficulty": "beginner",
                "exercise_count": 1,
                "exercise_types": ["recall"],
            },
        )
        assert drafted.status_code == 201
        body = drafted.json()
        assert body["status"] == "draft"
        assert body["source_type"] == "ai_generated"
        assert body["is_demo"] is False
        assert body["title"] == "Print a greeting"
        assert len(body["exercises"]) == 1
        assert body["exercises"][0]["status"] == "draft"
        assert body["exercises"][0]["data"]["prompt"] == "Print hello."
        edited = await request(
            client,
            "PATCH",
            f"/api/admin/lessons/{body['id']}",
            {"title": "Print a greeting, edited"},
        )
        assert edited.status_code == 200
        assert edited.json()["title"] == "Print a greeting, edited"
        assert edited.json()["status"] == "draft"

        mode["text"] = "this is not json"
        failed = await request(
            client,
            "POST",
            "/api/admin/ai/draft-lesson",
            {
                "module_id": module_id,
                "topic": "loops",
                "difficulty": "beginner",
                "exercise_count": 1,
                "exercise_types": ["recall"],
            },
        )
        assert failed.status_code == 422
        assert "Nothing was saved" in failed.json()["detail"]
        assert await lesson_count() == before + 1

        disabled = await request(
            client,
            "PUT",
            "/api/admin/ai/settings",
            {
                "provider": "ollama",
                "model": "llama3.2",
                "base_url": "http://127.0.0.1:11434",
                "enabled": False,
            },
        )
        assert disabled.status_code == 200
        calls_before = len(calls)
        blocked = await request(
            client,
            "POST",
            "/api/admin/ai/draft-lesson",
            {
                "module_id": module_id,
                "topic": "files",
                "difficulty": "beginner",
                "exercise_count": 1,
                "exercise_types": ["recall"],
            },
        )
        assert blocked.status_code == 400
        assert "Nothing was saved" in blocked.json()["detail"]
        assert len(calls) == calls_before
        assert await lesson_count() == before + 1

    async with get_sessionmaker()() as session:
        secret = await session.scalar(select(AppSetting).where(AppSetting.key == "ai_api_key"))
        assert secret is None
        audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.action.in_(
                            ["ai.draft", "ai.draft_rejected", "ai.settings_update", "ai.test"]
                        )
                    )
                )
            ).all()
        )
        blob = json.dumps([row.details for row in audits])
        assert API_KEY not in blob
        assert any(row.action == "ai.draft" and row.details["status"] == "draft" for row in audits)
        assert any(row.action == "ai.draft_rejected" for row in audits)
