"""Content CRUD, publishing, import/export, and starter lessons."""

import os
from contextlib import asynccontextmanager

import httpx
import pytest
import yaml
from app.db import get_sessionmaker
from app.main import app
from app.models.audit import AuditLog
from app.models.content import Exercise, Lesson
from app.services.seed import seed_starter_content
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


async def test_seed_is_idempotent(database) -> None:
    async with get_sessionmaker()() as session:
        await seed_starter_content(session)
        await seed_starter_content(session)
        count = await session.scalar(select(func.count()).select_from(Lesson))
        demos = await session.scalar(
            select(func.count()).select_from(Lesson).where(Lesson.is_demo.is_(True))
        )
    assert count == 67
    assert demos == 5


async def test_admin_builds_publishes_and_previews(database) -> None:
    async with api_client() as admin:
        await create_admin(admin)
        tree = await request(admin, "GET", "/api/admin/content/tree")
        assert tree.status_code == 200
        bash = next(track for track in tree.json()["tracks"] if track["slug"] == "bash")
        module = await request(
            admin,
            "POST",
            "/api/admin/modules",
            {"track_id": bash["id"], "title": "Practice", "description": "Extra"},
        )
        assert module.status_code == 201
        lesson = await request(
            admin,
            "POST",
            "/api/admin/lessons",
            {
                "module_id": module.json()["id"],
                "title": "All four",
                "summary": "Every exercise type",
                "body_markdown": "Type each one.",
            },
        )
        assert lesson.status_code == 201
        lesson_id = lesson.json()["id"]
        kinds = [
            (
                "trace",
                {
                    "type": "trace",
                    "prompt": "Type ls",
                    "code": "ls",
                    "check": {"accepted_answers": ["ls"]},
                },
            ),
            (
                "fill",
                {
                    "type": "fill",
                    "prompt": "Fill ls",
                    "code": "ls -la",
                    "blanks": [{"index": 2}],
                    "check": {"accepted_answers": ["ls -la"]},
                },
            ),
            ("recall", recall("Write ls", "ls")),
            (
                "challenge",
                {
                    "type": "challenge",
                    "prompt": "Quick ls",
                    "time_limit_seconds": 30,
                    "check": {"accepted_answers": ["ls"]},
                },
            ),
        ]
        for kind, data in kinds:
            created = await request(
                admin,
                "POST",
                "/api/admin/exercises",
                {"lesson_id": lesson_id, "data": data},
            )
            assert created.status_code == 201, created.text
            assert created.json()["type"] == kind
        unsafe = await request(
            admin,
            "POST",
            "/api/admin/exercises",
            {
                "lesson_id": lesson_id,
                "data": {
                    "type": "recall",
                    "prompt": "Unsafe",
                    "check": {"rules": [{"kind": "regex", "pattern": "(a+)+", "hint": "no"}]},
                },
            },
        )
        assert unsafe.status_code == 422
        checked = await request(
            admin,
            "POST",
            "/api/admin/exercises/test-check",
            {"attempt": "ls", "data": recall("Write ls", "ls")},
        )
        assert checked.status_code == 200
        assert checked.json()["passed"] is True
        missed = await request(
            admin,
            "POST",
            "/api/admin/exercises/test-check",
            {"attempt": "pwd", "data": recall("Write ls", "ls")},
        )
        assert missed.json()["passed"] is False
        hidden = await request(admin, "GET", f"/api/learn/lessons/{lesson_id}")
        assert hidden.status_code == 404
        published = await request(admin, "POST", f"/api/admin/lessons/{lesson_id}/publish")
        assert published.status_code == 200
        assert published.json()["status"] == "published"
        preview = await request(admin, "GET", f"/api/admin/lessons/{lesson_id}/preview")
        assert preview.status_code == 200
        recall_row = next(item for item in preview.json()["exercises"] if item["type"] == "recall")
        assert recall_row["code"] == ""
        assert "accepted_answers" not in preview.text
        visible = await request(admin, "GET", f"/api/learn/lessons/{lesson_id}")
        assert visible.status_code == 200
        outline = await request(admin, "GET", "/api/learn/tracks/bash/outline")
        titles = [
            lesson["title"]
            for module_row in outline.json()["modules"]
            for lesson in module_row["lessons"]
        ]
        assert "All four" in titles

    async with get_sessionmaker()() as session:
        audit = await session.scalar(select(AuditLog).where(AuditLog.action == "content.publish"))
        assert audit is not None
        assert audit.details["title"] == "All four"


async def test_export_import_round_trip(database) -> None:
    async with get_sessionmaker()() as session:
        await seed_starter_content(session)
        lesson_id = await session.scalar(select(Lesson.id).where(Lesson.title == "List the files"))
        exercise_id = await session.scalar(
            select(Exercise.id)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .where(Lesson.title == "List the files")
            .order_by(Exercise.position)
            .limit(1)
        )
    async with api_client() as admin:
        await create_admin(admin)
        exported = await request(admin, "GET", "/api/admin/export?track=bash&format=yaml")
        assert exported.status_code == 200
        original = yaml.safe_load(exported.text)
        preview = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": exported.text, "dry_run": True},
        )
        assert preview.status_code == 200
        assert preview.json()["dry_run"] is True
        assert preview.json()["mode"] == "extend"
        assert preview.json()["lessons"] == 6
        assert preview.json()["added_lessons"] == 0
        applied = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": exported.text, "dry_run": False},
        )
        assert applied.status_code == 200
        again = await request(admin, "GET", "/api/admin/export?track=bash&format=yaml")
        assert yaml.safe_load(again.text) == original
    async with get_sessionmaker()() as session:
        kept = await session.scalar(select(Lesson.id).where(Lesson.title == "List the files"))
        assert kept == lesson_id
        kept_exercise = await session.scalar(select(Exercise.id).where(Exercise.id == exercise_id))
        assert kept_exercise == exercise_id


def _titles(tree: dict, slug: str) -> list[str]:
    track = next(item for item in tree["tracks"] if item["slug"] == slug)
    return [lesson["title"] for module in track["modules"] for lesson in module["lessons"]]


EXTRA = """
slug: bash
name: Bash
description: The shell, one command at a time.
modules:
  - title: From a file
    description: Added by upload.
    status: published
    lessons:
      - title: Added by file
        summary: A lesson that was not in the starter set.
        body_markdown: Typed from a file.
        status: published
        is_demo: false
        exercises:
          - type: recall
            status: published
            prompt: Type the word file.
            order: 1
            check:
              mode: either
              accepted_answers:
                - file
"""


async def test_upload_extends_then_replace_is_explicit(database) -> None:
    async with get_sessionmaker()() as session:
        await seed_starter_content(session)
    async with api_client() as admin:
        await create_admin(admin)
        catalog = await request(admin, "GET", "/api/admin/export?track=all&format=json")
        assert catalog.status_code == 200
        slugs = {track["slug"] for track in catalog.json()["tracks"]}
        assert {"bash", "sql"} <= slugs
        tree = await request(admin, "GET", "/api/admin/content/tree")
        bash = next(track for track in tree.json()["tracks"] if track["slug"] == "bash")
        lesson = bash["modules"][0]["lessons"][0]
        one = await request(admin, "GET", f"/api/admin/export?lesson={lesson['id']}&format=yaml")
        assert one.status_code == 200
        one_doc = yaml.safe_load(one.text)
        assert one_doc["slug"] == "bash"
        assert len(one_doc["modules"]) == 1
        assert one_doc["modules"][0]["lessons"][0]["title"] == lesson["title"]

        preview = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": EXTRA, "dry_run": True, "mode": "extend"},
        )
        assert preview.status_code == 200
        assert preview.json()["added_lessons"] == 1
        before = await request(admin, "GET", "/api/admin/content/tree")
        assert "Added by file" not in _titles(before.json(), "bash")

        added = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": EXTRA, "dry_run": False, "mode": "extend"},
        )
        assert added.status_code == 200
        assert added.json()["added_lessons"] == 1
        again = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": EXTRA, "dry_run": False, "mode": "extend"},
        )
        assert again.json()["added_lessons"] == 0
        edited = EXTRA.replace(
            "A lesson that was not in the starter set.",
            "Edited in the file.",
        )
        updated = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": edited, "dry_run": False, "mode": "extend"},
        )
        assert updated.json()["added_lessons"] == 0
        assert updated.json()["updated_lessons"] == 1
        current = await request(admin, "GET", "/api/admin/content/tree")
        titles = _titles(current.json(), "bash")
        assert titles.count("Added by file") == 1
        assert "List the files" in titles
        bash_now = next(track for track in current.json()["tracks"] if track["slug"] == "bash")
        added_lesson = next(
            item
            for module in bash_now["modules"]
            for item in module["lessons"]
            if item["title"] == "Added by file"
        )
        assert added_lesson["summary"] == "Edited in the file."
        assert len(_titles(current.json(), "sql")) == 43

        replaced = await request(
            admin,
            "POST",
            "/api/admin/import",
            {"document": EXTRA, "dry_run": False, "mode": "replace"},
        )
        assert replaced.status_code == 200
        after = await request(admin, "GET", "/api/admin/content/tree")
        assert _titles(after.json(), "bash") == ["Added by file"]
        assert len(_titles(after.json(), "sql")) == 43
