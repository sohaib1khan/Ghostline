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


# Tracks without a browser live-tracer get notes-only step-through from tokens/code
# until recorded steps are imported (same UX shape as Go).
_SYNTHETIC_TRACKS = frozenset(
    {"javascript", "sql", "bash", "csharp", "java", "go"}
)


def synthetic_walkthrough(data: dict, track_slug: str | None) -> dict | None:
    """Build a notes-only walkthrough when authors have not added one yet."""
    if data.get("walkthrough"):
        return None
    slug = (track_slug or "").lower()
    if slug not in _SYNTHETIC_TRACKS:
        return None
    program, _source_lines = build_walkthrough_program(data)
    lines = program.splitlines() if program else []
    if not any(line.strip() for line in lines):
        return None
    notes: dict[int, str] = {}
    for token in data.get("tokens") or []:
        match = str(token.get("match") or "").strip()
        explain = str(token.get("explain") or "").strip()
        if not match or not explain:
            continue
        for index, line in enumerate(lines, 1):
            if match in line and index not in notes:
                notes[index] = explain[:300]
                break
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        if index not in notes:
            notes[index] = "Watch what this line does."
    if not notes:
        return None
    return {
        "setup": "",
        "given": "",
        "try_it": "",
        "run": False,
        "stdin": [],
        "args": [],
        "files": {},
        "notes": notes,
        "steps": [],
        "stdout": data.get("simulated_output"),
        "stderr": None,
        "exit_code": None,
        "nondeterministic": False,
        "source_sha": None,
        "expect_error": None,
    }


def has_walkthrough_payload(data: dict, track_slug: str | None = None) -> bool:
    if data.get("walkthrough"):
        return True
    return synthetic_walkthrough(data, track_slug) is not None


def walkthrough_mode(data: dict, track_slug: str | None = None) -> str | None:
    """recorded | notes | live — drives learner button labels."""
    walk = data.get("walkthrough")
    if walk:
        if walk.get("steps"):
            return "recorded"
        if walk.get("run") is False:
            return "notes"
        return "live"
    if synthetic_walkthrough(data, track_slug):
        return "notes"
    return None


def serialize_walkthrough(data: dict, *, track_slug: str | None = None) -> dict | None:
    walk = data.get("walkthrough")
    if not walk:
        walk = synthetic_walkthrough(data, track_slug)
        if not walk:
            return None
        data = {**data, "walkthrough": walk}
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
    track_slug = None
    if exercise.lesson and exercise.lesson.module and exercise.lesson.module.track:
        track_slug = exercise.lesson.module.track.slug

    if not has_walkthrough_payload(data, track_slug):
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

    payload = serialize_walkthrough(data, track_slug=track_slug)
    if payload is None:
        raise ContentError(404, "This exercise has no walkthrough.")
    # Mark synthetic so the UI can show language-aware copy.
    if not (data.get("walkthrough")):
        payload["synthetic"] = True
    return payload
