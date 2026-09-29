"""Check submissions, XP, and the learner dashboard."""

import os
from contextlib import asynccontextmanager

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.services.notifications.dispatcher import flush_notifications
from app.services.setup import ensure_setup_token
from app.services.tracks import ensure_tracks
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
LEARNER_EMAIL = "progress-learner@example.com"
PASSWORD = "correct-horse-battery"


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


def recall(prompt: str, answer: str, xp: int = 10) -> dict:
    return {
        "type": "recall",
        "prompt": prompt,
        "xp": xp,
        "check": {"mode": "either", "accepted_answers": [answer]},
    }


async def publish_recall(client: httpx.AsyncClient, slug: str, title: str, data: dict) -> str:
    tree = await request(client, "GET", "/api/admin/content/tree")
    track = next(item for item in tree.json()["tracks"] if item["slug"] == slug)
    module = await request(
        client,
        "POST",
        "/api/admin/modules",
        {"track_id": track["id"], "title": title},
    )
    assert module.status_code == 201
    lesson = await request(
        client,
        "POST",
        "/api/admin/lessons",
        {"module_id": module.json()["id"], "title": title},
    )
    assert lesson.status_code == 201
    lesson_id = lesson.json()["id"]
    created = await request(
        client,
        "POST",
        "/api/admin/exercises",
        {"lesson_id": lesson_id, "data": data},
    )
    assert created.status_code == 201, created.text
    published = await request(client, "POST", f"/api/admin/lessons/{lesson_id}/publish")
    assert published.status_code == 200
    return created.json()["id"]


async def test_check_awards_xp_once_and_dashboard_continues(database) -> None:
    async with api_client() as admin, api_client() as learner:
        await create_admin(admin)
        first = await publish_recall(admin, "bash", "First", recall("List", "ls", xp=10))
        second = await publish_recall(admin, "bash", "Second", recall("Print", "pwd", xp=10))
        other = await publish_recall(admin, "python", "Away", recall("Print", "print(1)"))
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
                "track_slugs": ["bash"],
            },
        )
        assert created.status_code == 201
        logged_in = await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        assert logged_in.status_code == 200

        missed = await request(learner, "POST", f"/api/check/{first}", {"attempt": "pwd"})
        assert missed.status_code == 200
        assert missed.json()["passed"] is False
        assert missed.json()["xp_awarded"] == 0
        assert missed.json()["status"] == "started"

        hinted = await request(
            learner,
            "POST",
            f"/api/check/{first}",
            {"attempt": "pwd", "hints_used": 2},
        )
        assert hinted.json()["passed"] is False

        passed = await request(
            learner,
            "POST",
            f"/api/check/{first}",
            {"attempt": "ls", "wpm": 40, "accuracy": 90},
        )
        assert passed.status_code == 200
        body = passed.json()
        assert body["passed"] is True
        assert body["xp_awarded"] == 6
        assert body["xp_total"] == 6
        assert body["status"] == "completed"
        assert body["failed_rule_hint"] is None

        again = await request(learner, "POST", f"/api/check/{first}", {"attempt": "ls", "wpm": 80})
        assert again.json()["xp_awarded"] == 0
        assert again.json()["xp_total"] == 6

        blocked = await request(learner, "POST", f"/api/check/{other}", {"attempt": "print(1)"})
        assert blocked.status_code == 403

        board = await request(learner, "GET", "/api/learn/dashboard")
        assert board.status_code == 200
        payload = board.json()
        assert payload["xp"] == 6
        assert payload["current_streak_days"] == 1
        bash = next(track for track in payload["tracks"] if track["slug"] == "bash")
        assert bash["completed"] == 1
        assert bash["total"] >= 2
        assert bash["continue_lesson_id"]
        assert "python" not in {track["slug"] for track in payload["tracks"]}

        outline = await request(learner, "GET", "/api/learn/tracks/bash/outline")
        lessons = [lesson for module in outline.json()["modules"] for lesson in module["lessons"]]
        by_title = {lesson["title"]: lesson["progress"] for lesson in lessons}
        assert by_title["First"] == "done"
        assert by_title["Second"] == "new"

        finished = await request(learner, "POST", f"/api/check/{second}", {"attempt": "pwd"})
        assert finished.json()["xp_awarded"] == 10
        assert finished.json()["xp_total"] == 16
        later = await request(learner, "GET", "/api/learn/dashboard")
        bash = next(track for track in later.json()["tracks"] if track["slug"] == "bash")
        assert bash["completed"] == 2


async def test_output_is_compared_and_drafts_stay_hidden(database) -> None:
    async with api_client() as admin, api_client() as learner:
        await create_admin(admin)
        tree = await request(admin, "GET", "/api/admin/content/tree")
        bash = next(item for item in tree.json()["tracks"] if item["slug"] == "bash")
        module = await request(
            admin, "POST", "/api/admin/modules", {"track_id": bash["id"], "title": "Run"}
        )
        lesson = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {"module_id": module.json()["id"], "title": "Print"},
        )
        lesson_id = lesson.json()["id"]
        draft = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {
                "lesson_id": lesson_id,
                "data": {
                    "type": "recall",
                    "prompt": "Print hi",
                    "runtime": "browser_js",
                    "expected_output": "hi",
                    "check": {
                        "mode": "rules",
                        "rules": [{"kind": "output_equals", "hint": "Print hi"}],
                    },
                },
            },
        )
        assert draft.status_code == 201, draft.text
        exercise_id = draft.json()["id"]
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
                "track_slugs": ["bash"],
            },
        )
        assert created.status_code == 201
        await request(
            learner,
            "POST",
            "/api/auth/login",
            {"email": LEARNER_EMAIL, "password": PASSWORD},
        )
        hidden = await request(
            learner,
            "POST",
            f"/api/check/{exercise_id}",
            {"attempt": "console.log('hi')", "output": "hi"},
        )
        assert hidden.status_code == 404
        published = await request(admin, "POST", f"/api/admin/lessons/{lesson_id}/publish")
        assert published.status_code == 200
        wrong = await request(
            learner,
            "POST",
            f"/api/check/{exercise_id}",
            {"attempt": "console.log('hi')", "output": "no"},
        )
        assert wrong.json()["passed"] is False
        assert wrong.json()["failed_kind"] == "output_equals"
        right = await request(
            learner,
            "POST",
            f"/api/check/{exercise_id}",
            {"attempt": "console.log('hi')", "output": "hi"},
        )
        assert right.json()["passed"] is True
        assert right.json()["xp_awarded"] == 10
