"""HTTP tests for server-graded module boss."""

import os
from contextlib import asynccontextmanager

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.services.boss import item_credit
from app.services.notifications.dispatcher import flush_notifications
from app.services.setup import ensure_setup_token
from app.services.tracks import ensure_tracks
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "boss-admin@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture
async def database():
    async with get_sessionmaker()() as session:
        await session.execute(
            text(
                "TRUNCATE audit_log, sessions, app_settings, users, notification_channels, "
                "practice_events, exercise_progress, attempt_log, user_stats, boss_runs, "
                "module_progress, exercises, lessons, modules, content_revisions, "
                "user_track_access RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
        await ensure_tracks(session)
    yield
    await flush_notifications()


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
            "first_name": "Boss",
            "last_name": "Admin",
            "email": ADMIN_EMAIL,
            "password": PASSWORD,
        },
    )
    assert created.status_code == 201
    logged_in = await request(
        client, "POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert logged_in.status_code == 200


def recall(prompt: str, answer: str, *, boss_hints: list[str] | None = None) -> dict:
    data = {
        "type": "recall",
        "prompt": prompt,
        "xp": 10,
        "check": {"mode": "answers", "accepted_answers": [answer]},
    }
    if boss_hints is not None:
        data["boss_hints"] = boss_hints
    return data


async def publish_module_with_recalls(client: httpx.AsyncClient) -> str:
    tree = await request(client, "GET", "/api/admin/content/tree")
    track = next(item for item in tree.json()["tracks"] if item["slug"] == "python")
    module = await request(
        client,
        "POST",
        "/api/admin/modules",
        {"track_id": track["id"], "title": "Boss module"},
    )
    assert module.status_code == 201
    module_id = module.json()["id"]
    lesson = await request(
        client,
        "POST",
        "/api/admin/lessons",
        {
            "module_id": module_id,
            "title": "Keyword bundles",
            "summary": "kwargs packs names",
        },
    )
    assert lesson.status_code == 201
    lesson_id = lesson.json()["id"]
    answers = [
        (
            "Print hi",
            "print('hi')",
            ["Remind: print shows text.", "You need:\n- print", "```\n___(___)\n```"],
        ),
        (
            "Name x",
            "x = 1",
            ["From lesson: names.", "You need:\n- =", "```\n___ = ___\n```"],
        ),
        ("Add", "1 + 1", None),
        ("Len", "len([])", None),
        ("Bool", "True", None),
    ]
    for prompt, answer, hints in answers:
        created = await request(
            client,
            "POST",
            "/api/admin/exercises",
            {"lesson_id": lesson_id, "data": recall(prompt, answer, boss_hints=hints)},
        )
        assert created.status_code == 201, created.text
    published = await request(client, "POST", f"/api/admin/lessons/{lesson_id}/publish")
    assert published.status_code == 200
    return module_id


async def test_boss_start_hints_check_finish(database) -> None:
    async with api_client() as client:
        await create_admin(client)
        module_id = await publish_module_with_recalls(client)
        started = await request(client, "POST", f"/api/learn/modules/{module_id}/boss/start")
        assert started.status_code == 200, started.text
        body = started.json()
        assert "run_id" in body
        assert body["items"]
        for item in body["items"]:
            assert "ghost" not in item
            assert "answer" not in item
            assert "hint_count" in item
            assert "hint_costs" in item
            blob = str(item)
            assert "print('hi')" not in blob
            assert "x = 1" not in blob

        run_id = body["run_id"]
        first = body["items"][0]
        assert first["hint_count"] >= 2

        skip = await request(
            client,
            "POST",
            f"/api/learn/modules/{module_id}/boss/{run_id}/hint",
            {"exercise_id": first["id"], "level": 2},
        )
        assert skip.status_code == 400

        step1 = await request(
            client,
            "POST",
            f"/api/learn/modules/{module_id}/boss/{run_id}/hint",
            {"exercise_id": first["id"], "level": 1},
        )
        assert step1.status_code == 200, step1.text
        assert "text" in step1.json()
        assert "print('hi')" not in step1.json()["text"]

        bad = await request(
            client,
            "POST",
            f"/api/learn/modules/{module_id}/boss/{run_id}/check",
            {"exercise_id": first["id"], "attempt": "nope"},
        )
        assert bad.status_code == 200
        msg = bad.json()["message"]
        assert "print('hi')" not in msg

        for item in body["items"]:
            await request(
                client,
                "POST",
                f"/api/learn/modules/{module_id}/boss/{run_id}/reveal",
                {"exercise_id": item["id"]},
            )
        finished = await request(
            client, "POST", f"/api/learn/modules/{module_id}/boss/{run_id}/finish"
        )
        assert finished.status_code == 200, finished.text
        summary = finished.json()
        assert summary["score"] == 0
        assert summary["passed"] is False
        assert all(float(entry["credit"]) == 0 for entry in summary["items"])
        # Old client-trusted submit route is gone.
        legacy = await request(
            client,
            "POST",
            f"/api/learn/modules/{module_id}/boss",
            {"results": [{"exercise_id": first["id"], "passed": True}]},
        )
        assert legacy.status_code == 404


def test_credit_helpers_match_spec() -> None:
    assert item_credit(hint_level=0, tries=1, passed=True, revealed=False) == 1.0
    assert item_credit(hint_level=3, tries=1, passed=True, revealed=False) == 0.5
    assert item_credit(hint_level=1, tries=2, passed=True, revealed=False) == 0.45
    assert item_credit(hint_level=0, tries=1, passed=False, revealed=True) == 0.0
