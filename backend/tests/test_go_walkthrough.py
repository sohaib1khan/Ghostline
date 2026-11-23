"""Static checks for recorded Go walkthroughs, quizzes, and boss hints.

No Go toolchain required — recordings are already in the seed YAML.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from app.schemas.content import ExerciseData
from app.services.walkthrough import build_walkthrough_program, program_sha, serialize_walkthrough

SEED = Path(__file__).resolve().parents[1] / "app" / "seed" / "lessons" / "go.yaml"


def _exercises():
    if not SEED.exists():
        return []
    doc = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    rows = []
    for module in doc.get("modules") or []:
        for lesson in module.get("lessons") or []:
            for exercise in lesson.get("exercises") or []:
                rows.append((lesson.get("title") or "lesson", exercise))
    return rows


_ROWS = _exercises()


@pytest.mark.skipif(not _ROWS, reason="go.yaml seed missing")
def test_go_seed_validates_as_exercise_data() -> None:
    errors = []
    for title, exercise in _ROWS:
        try:
            ExerciseData.model_validate(
                {k: v for k, v in exercise.items() if k not in {"status", "order"}}
            )
        except Exception as exc:  # noqa: BLE001 - collect all failures
            errors.append(f"{title}: {exc}")
            if len(errors) >= 8:
                break
    assert not errors, "\n".join(errors)


@pytest.mark.skipif(not _ROWS, reason="go.yaml seed missing")
@pytest.mark.parametrize(("title", "exercise"), _ROWS[:40] or [pytest.param(None, None, id="none")])
def test_go_walkthrough_notes_and_steps(title, exercise) -> None:
    walk = exercise.get("walkthrough")
    if not walk:
        pytest.skip("no walkthrough")
    program, _ = build_walkthrough_program(exercise)
    lines = program.splitlines()
    notes = walk.get("notes") or {}
    for number, text in enumerate(lines, 1):
        if text.strip() and not text.strip().startswith("//"):
            assert number in notes or str(number) in notes, (
                f"{title}: line {number} has no note: {text!r}"
            )
    steps = walk.get("steps") or []
    if walk.get("run") is False and not steps:
        return
    if not steps:
        pytest.skip("notes-only walkthrough")
    assert steps[-1].get("event") == "end"
    stdout = str(walk.get("stdout") or "")
    stderr = str(walk.get("stderr") or "")
    prev_out = prev_err = -1
    for step in steps:
        assert 1 <= int(step["line"]) <= max(len(lines), 1)
        out_len = int(step.get("stdout_len") or 0)
        err_len = int(step.get("stderr_len") or 0)
        assert out_len >= prev_out
        assert err_len >= prev_err
        prev_out, prev_err = out_len, err_len
    assert steps[-1].get("stdout_len", 0) == len(stdout)
    assert steps[-1].get("stderr_len", 0) == len(stderr)
    assert walk.get("source_sha") == program_sha(program)


@pytest.mark.skipif(not _ROWS, reason="go.yaml seed missing")
def test_go_quiz_and_boss_hints_safe() -> None:
    for title, exercise in _ROWS:
        data = {k: v for k, v in exercise.items() if k not in {"status", "order"}}
        answers = [
            str(item).strip()
            for item in ((data.get("check") or {}).get("accepted_answers") or [])
            if str(item).strip()
        ]
        for item in data.get("quiz") or []:
            right = str(item.get("answer") or "")
            wrong = [str(w) for w in (item.get("wrong") or [])]
            assert right not in wrong, f"{title}: quiz answer listed as wrong"
        for step in data.get("boss_hints") or []:
            text = str(step)
            for answer in answers:
                if len(answer) >= 8 and answer in text:
                    raise AssertionError(f"{title}: boss hint leaks answer {answer!r}")
            if "```" in text or "___" in text:
                assert text.count("___") >= 2, f"{title}: shape step needs ≥2 blanks"


def test_recorded_serialize_marks_stale_on_sha_mismatch() -> None:
    payload = serialize_walkthrough(
        {
            "code": 'fmt.Println("hi")\n',
            "walkthrough": {
                "notes": {1: "Print."},
                "source_sha": "0000000000000000",
                "stdout": "hi\n",
                "steps": [
                    {
                        "line": 1,
                        "event": "line",
                        "globals": {},
                        "frames": [],
                        "stdout_len": 0,
                        "stderr_len": 0,
                    },
                    {
                        "line": 1,
                        "event": "end",
                        "globals": {},
                        "frames": [],
                        "stdout_len": 3,
                        "stderr_len": 0,
                    },
                ],
            },
        },
        track_slug="go",
    )
    assert payload is not None
    assert payload["stale"] is True
    assert payload["steps"] == []
    assert payload["stdout"] is None
    assert payload["track_slug"] == "go"


def test_program_sha_stable() -> None:
    assert len(program_sha("fmt.Println(1)")) == 16
    assert program_sha("a") != program_sha("b")
    assert hashlib.sha256(b"x").hexdigest()[:16] == program_sha("x")
