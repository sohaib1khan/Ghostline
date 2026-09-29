"""Public demo catalog, checks, and the demo rate limit."""

import os
from contextlib import asynccontextmanager

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.models.progress import ExerciseProgress
from app.security.rate_limit import limiter
from app.services.setup import ensure_setup_token
from app.services.tracks import ensure_tracks
from sqlalchemy import func, select, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
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


def recall(prompt: str, answer: str) -> dict:
    return {
        "type": "recall",
        "prompt": prompt,
        "check": {"mode": "either", "accepted_answers": [answer]},
    }


async def progress_count(exercise_id: str) -> int:
    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(ExerciseProgress)
            .where(ExerciseProgress.exercise_id == exercise_id)
        )
    return int(count or 0)


async def test_demo_hides_private_lessons_and_does_not_save_progress(database) -> None:
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        tree = await request(admin, "GET", "/api/admin/content/tree")
        bash = next(track for track in tree.json()["tracks"] if track["slug"] == "bash")
        module = await request(
            admin,
            "POST",
            "/api/admin/modules",
            {"track_id": bash["id"], "title": "Demo lab", "description": "Public"},
        )
        assert module.status_code == 201
        demo = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {
                "module_id": module.json()["id"],
                "title": "Public ls",
                "summary": "Try ls",
                "body_markdown": "Type the listing command.",
                "is_demo": True,
            },
        )
        assert demo.status_code == 201
        demo_id = demo.json()["id"]
        exercise = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {"lesson_id": demo_id, "data": recall("Write ls", "ls")},
        )
        assert exercise.status_code == 201
        exercise_id = exercise.json()["id"]
        published = await request(admin, "POST", f"/api/admin/lessons/{demo_id}/publish")
        assert published.status_code == 200

        private = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {
                "module_id": module.json()["id"],
                "title": "Private notes",
                "summary": "Not a demo",
                "is_demo": False,
            },
        )
        assert private.status_code == 201
        private_id = private.json()["id"]
        private_exercise = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {"lesson_id": private_id, "data": recall("Write pwd", "pwd")},
        )
        assert private_exercise.status_code == 201
        private_exercise_id = private_exercise.json()["id"]
        private_published = await request(admin, "POST", f"/api/admin/lessons/{private_id}/publish")
        assert private_published.status_code == 200

        catalog = await request(guest, "GET", "/api/demo/tracks")
        assert catalog.status_code == 200
        titles = [
            lesson["title"] for track in catalog.json()["tracks"] for lesson in track["lessons"]
        ]
        assert "Public ls" in titles
        assert "List the files" in titles
        assert "Private notes" not in titles

        opened = await request(guest, "GET", f"/api/demo/lessons/{demo_id}")
        assert opened.status_code == 200
        body = opened.json()
        assert body["is_demo"] is True
        assert "accepted_answers" not in opened.text
        assert body["exercises"][0]["code"] == ""

        hidden = await request(guest, "GET", f"/api/demo/lessons/{private_id}")
        assert hidden.status_code == 404

        missed = await request(guest, "POST", f"/api/demo/check/{exercise_id}", {"attempt": "pwd"})
        assert missed.status_code == 200
        assert missed.json()["passed"] is False
        assert missed.json()["xp_awarded"] == 0

        passed = await request(guest, "POST", f"/api/demo/check/{exercise_id}", {"attempt": "ls"})
        assert passed.status_code == 200
        assert passed.json()["passed"] is True
        assert passed.json()["xp_awarded"] == 0
        assert "xp_total" not in passed.json()

        signed_in = await request(
            admin, "POST", f"/api/demo/check/{exercise_id}", {"attempt": "ls"}
        )
        assert signed_in.status_code == 200
        assert await progress_count(exercise_id) == 0

        blocked = await request(
            guest, "POST", f"/api/demo/check/{private_exercise_id}", {"attempt": "pwd"}
        )
        assert blocked.status_code == 404


async def test_demo_check_rate_limit(database) -> None:
    async with api_client() as admin, api_client() as guest:
        await create_admin(admin)
        tree = await request(admin, "GET", "/api/admin/content/tree")
        bash = next(track for track in tree.json()["tracks"] if track["slug"] == "bash")
        module = await request(
            admin,
            "POST",
            "/api/admin/modules",
            {"track_id": bash["id"], "title": "Limit lab", "description": "Rate"},
        )
        lesson = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {
                "module_id": module.json()["id"],
                "title": "Limited ls",
                "is_demo": True,
            },
        )
        exercise = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {"lesson_id": lesson.json()["id"], "data": recall("Write ls", "ls")},
        )
        published = await request(
            admin, "POST", f"/api/admin/lessons/{lesson.json()['id']}/publish"
        )
        assert published.status_code == 200
        exercise_id = exercise.json()["id"]
        headers = await csrf_headers(guest)
        limiter.enabled = True
        limiter.reset()
        statuses = []
        for _ in range(31):
            response = await guest.post(
                f"/api/demo/check/{exercise_id}",
                json={"attempt": "ls"},
                headers=headers,
            )
            statuses.append(response.status_code)
        assert statuses[:30] == [200] * 30
        assert statuses[30] == 429
