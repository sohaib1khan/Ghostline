"""Build and authorize Ghostline step-through (walkthrough) payloads."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.progress import ExerciseProgress
from app.models.user import User
from app.services.content_store import ContentError


def build_walkthrough_program(data: dict) -> tuple[str, int]:
    """Return (program, source_line_count).

    source is exercise.code, or the first accepted answer when code is empty.
    try_it lines are appended so a def can actually run.
    """
    check = data.get("check") or {}
    answers = check.get("accepted_answers") or []
    source = str(data.get("code") or "").rstrip("\n")
    if not source.strip():
        for item in answers:
            sample = str(item).rstrip("\n")
            if sample.strip():
                source = sample
                break
    walk = data.get("walkthrough") or {}
    try_it = str(walk.get("try_it") or "").strip("\n")
    source_lines = len(source.splitlines()) if source else 0
    if try_it:
        program = source.rstrip("\n") + "\n\n" + try_it
    else:
        program = source
    return program, source_lines


def program_sha(program: str) -> str:
    return hashlib.sha256(program.encode("utf-8")).hexdigest()[:16]


def serialize_walkthrough(data: dict, *, track_slug: str | None = None) -> dict | None:
    walk = data.get("walkthrough")
    if not walk:
        return None
    program, source_lines = build_walkthrough_program(data)
    notes = walk.get("notes") or {}
    notes_out = {int(key): str(value) for key, value in notes.items()}
    steps = list(walk.get("steps") or [])
    stdout = walk.get("stdout")
    stderr = walk.get("stderr")
    source_sha = walk.get("source_sha")
    stale = False
    if steps:
        expected = program_sha(program)
        if source_sha and str(source_sha) != expected:
            stale = True
            steps = []
            stdout = None
            stderr = None

    files = walk.get("files") or {}
    files_out = {str(key): str(value) for key, value in files.items()}

    return {
        "program": program,
        "source_lines": source_lines,
        "setup": str(walk.get("setup") or ""),
        "given": str(walk.get("given") or ""),
        "stdin": list(walk.get("stdin") or []),
        "args": [str(item) for item in (walk.get("args") or [])],
        "files": files_out,
        "run": bool(walk.get("run", True)),
        "expect_error": walk.get("expect_error"),
        "stdout": None if stdout is None else str(stdout),
        "stderr": None if stderr is None else str(stderr),
        "exit_code": walk.get("exit_code"),
        "nondeterministic": bool(walk.get("nondeterministic")),
        "source_sha": source_sha,
        "steps": steps,
        "stale": stale,
        "recorded": bool(steps) and not stale,
        "notes": notes_out,
        "track_slug": (track_slug or "").lower() or None,
    }


async def walkthrough_for_user(
    session: AsyncSession,
    user: User,
    exercise_id: uuid.UUID,
    *,
    hints_opened: int = 0,
) -> dict:
    exercise = await session.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.lesson)
            .selectinload(Lesson.module)
            .selectinload(Module.track)
        )
    )
    if exercise is None or exercise.status != "published":
        raise ContentError(404, "Exercise not found")
    data = exercise.data or {}
    if not data.get("walkthrough"):
        raise ContentError(404, "This exercise has no walkthrough.")

    if exercise.type in {"trace", "fill"}:
        allowed = True
    else:
        progress = await session.scalar(
            select(ExerciseProgress).where(
                ExerciseProgress.user_id == user.id,
                ExerciseProgress.exercise_id == exercise.id,
            )
        )
        hints = list(data.get("hints") or [])
        opened_final = bool(hints) and int(hints_opened or 0) >= len(hints)
        used_final = bool(hints) and progress is not None and int(progress.hints_used or 0) >= len(
            hints
        )
        passed = bool(progress and progress.status == "completed")
        allowed = passed or opened_final or used_final

    if not allowed:
        raise ContentError(403, "Finish this exercise to step through it.")

    track_slug = None
    if exercise.lesson and exercise.lesson.module and exercise.lesson.module.track:
        track_slug = exercise.lesson.module.track.slug

    payload = serialize_walkthrough(data, track_slug=track_slug)
    if payload is None:
        raise ContentError(404, "This exercise has no walkthrough.")
    return payload
