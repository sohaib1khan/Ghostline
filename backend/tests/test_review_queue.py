"""Review due queue only includes practiced courses."""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.db import get_sessionmaker
from app.main import app
from app.models.progress import ExerciseProgress
from app.models.track import Track
from app.routers.review import practiced_track_ids
from app.services.tracks import ensure_tracks
from sqlalchemy import select, text
from tests.test_progress import PASSWORD, create_admin, publish_recall, recall, request

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run database tests",
)

LEARNER_EMAIL = "review-queue-learner@example.com"


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


async def test_review_due_only_includes_practiced_tracks(database) -> None:
    async with api_client() as admin, api_client() as learner:
        await create_admin(admin)
        bash_ex = await publish_recall(admin, "bash", "Bash one", recall("List", "ls", xp=10))
        await publish_recall(admin, "python", "Py one", recall("Print", "print(1)", xp=10))
        created = await request(
            admin,
            "POST",
            "/api/admin/users",
            {
                "first_name": "Review",
                "last_name": "Only",
                "email": LEARNER_EMAIL,
                "password": PASSWORD,
                "role": "learner",
                "track_slugs": ["bash", "python"],
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

        passed = await request(learner, "POST", f"/api/check/{bash_ex}", {"attempt": "ls"})
        assert passed.status_code == 200
        assert passed.json()["passed"] is True

        async with get_sessionmaker()() as session:
            progress = await session.scalar(
                select(ExerciseProgress).where(ExerciseProgress.exercise_id == bash_ex)
            )
            assert progress is not None
            progress.next_review_at = datetime.now(UTC) - timedelta(hours=1)
            await session.commit()

            tracks = list((await session.scalars(select(Track))).all())
            visible = {track.id for track in tracks}
            started = await practiced_track_ids(session, progress.user_id, visible)
            bash = next(track for track in tracks if track.slug == "bash")
            python = next(track for track in tracks if track.slug == "python")
            assert bash.id in started
            assert python.id not in started

        due = await request(learner, "GET", "/api/review/due?limit=20")
        assert due.status_code == 200
        body = due.json()
        exercise_items = [item for item in body["due"] if item.get("kind") == "exercise"]
        assert exercise_items
        assert all(item["track_slug"] == "bash" for item in exercise_items)
        assert all(item["track_slug"] != "python" for item in exercise_items)
