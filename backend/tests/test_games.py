"""Games stay inside permitted published exercises, and stats follow the score."""

import os
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.models.content import Exercise
from app.services.setup import ensure_setup_token
from app.services.tracks import ensure_tracks
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

ADMIN_EMAIL = "ada@example.com"
LEARNER_EMAIL = "games-learner@example.com"
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


async def exercise_data(exercise_id: str) -> dict:
    async with get_sessionmaker()() as session:
        row = await session.get(Exercise, UUID(exercise_id))
        assert row is not None
        return dict(row.data)


async def test_games_score_once_and_stats_follow(database) -> None:
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

        denied = await request(learner, "GET", "/api/games/next?game=speed_drill&track=python")
        assert denied.status_code == 403
        roulette = await request(learner, "GET", "/api/games/next?game=command_roulette")
        assert roulette.status_code == 200
        assert roulette.json()["track_slug"] == "bash"
        assert "accepted_answers" not in roulette.text

        drilled = await request(learner, "GET", "/api/games/next?game=speed_drill&track=bash")
        assert drilled.status_code == 200
        body = drilled.json()
        assert body["code"]
        assert "accepted_answers" not in drilled.text
        exercise_id = body["exercise_id"]
        answer = (await exercise_data(exercise_id))["code"]

        hunted = await request(learner, "GET", "/api/games/next?game=bug_hunt&track=bash")
        assert hunted.status_code == 200
        hunt = hunted.json()
        assert "code" not in hunt
        assert "broken" in hunt
        real = (await exercise_data(hunt["exercise_id"]))["code"]
        assert hunt["broken"] != real

        missed = await request(
            learner,
            "POST",
            f"/api/games/score/{exercise_id}",
            {"game": "speed_drill", "attempt": "nope", "wpm": 10, "accuracy": 0},
        )
        assert missed.status_code == 200
        assert missed.json()["passed"] is False
        assert missed.json()["xp_awarded"] == 0

        passed = await request(
            learner,
            "POST",
            f"/api/games/score/{exercise_id}",
            {"game": "speed_drill", "attempt": answer, "wpm": 42, "accuracy": 100},
        )
        assert passed.status_code == 200
        assert passed.json()["passed"] is True
        assert passed.json()["xp_awarded"] == 5

        again = await request(
            learner,
            "POST",
            f"/api/games/score/{exercise_id}",
            {"game": "speed_drill", "attempt": answer, "wpm": 50, "accuracy": 100},
        )
        assert again.json()["xp_awarded"] == 0

        tree = await request(admin, "GET", "/api/admin/content/tree")
        go = next(item for item in tree.json()["tracks"] if item["slug"] == "go")
        module = await request(
            admin, "POST", "/api/admin/modules", {"track_id": go["id"], "title": "Hidden"}
        )
        lesson = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {"module_id": module.json()["id"], "title": "Draft line"},
        )
        draft = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {
                "lesson_id": lesson.json()["id"],
                "data": {
                    "type": "trace",
                    "prompt": "Type hi",
                    "code": "echo hi",
                    "check": {"accepted_answers": ["echo hi"]},
                },
            },
        )
        hidden = await request(
            learner,
            "POST",
            f"/api/games/score/{draft.json()['id']}",
            {"game": "speed_drill", "attempt": "echo hi"},
        )
        assert hidden.status_code == 404

        stats = await request(learner, "GET", "/api/me/stats")
        assert stats.status_code == 200
        payload = stats.json()
        assert payload["games_played"] >= 1
        assert payload["xp"] == 5
        assert payload["wpm_trend"][-1]["wpm"] == 46
        assert payload["current_streak_days"] == 1

        closed = await request(learner, "GET", "/api/games/leaderboard")
        assert closed.status_code == 404
        opened = await request(admin, "PUT", "/api/admin/settings", {"leaderboard_enabled": True})
        assert opened.status_code == 200
        board = await request(learner, "GET", "/api/games/leaderboard")
        assert board.status_code == 200
        assert board.json()["entries"][0]["name"] == "Grace"
        assert LEARNER_EMAIL not in board.text
        shut = await request(admin, "PUT", "/api/admin/settings", {"leaderboard_enabled": False})
        assert shut.status_code == 200
        assert (await request(learner, "GET", "/api/games/leaderboard")).status_code == 404
