"""Walkthrough (step-through) tests. Copy to backend/tests/test_walkthrough.py.

The tracer itself only ever runs in the browser sandbox. These tests load the
same file to prove every seeded walkthrough runs and matches its lesson.
"""

import importlib.util
import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TRACER = ROOT / "frontend" / "public" / "sandbox" / "tracer.py"
SEED = ROOT / "backend" / "app" / "seed" / "lessons"

pytestmark = pytest.mark.skipif(not TRACER.exists(), reason="frontend not in this checkout")


def _tracer():
    spec = importlib.util.spec_from_file_location("ghostline_tracer", TRACER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walkthroughs():
    for path in sorted(SEED.glob("*.yaml")):
        track = yaml.safe_load(path.read_text(encoding="utf-8"))
        for module in track.get("modules", []):
            for lesson in module["lessons"]:
                for exercise in lesson["exercises"]:
                    if "walkthrough" in exercise:
                        yield pytest.param(lesson["title"], exercise, id=f"{path.stem}:{lesson['title']}:{exercise['order']}")


def _program(exercise):
    source = exercise.get("code") or exercise["check"]["accepted_answers"][0]
    try_it = exercise["walkthrough"].get("try_it")
    return source.rstrip("\n") + ("\n\n" + try_it if try_it else "")


_SEEDED = list(_walkthroughs())


@pytest.mark.skipif(not _SEEDED, reason="No seeded walkthroughs yet — import python.yaml via Studio")
@pytest.mark.parametrize(("title", "exercise"), _SEEDED or [pytest.param(None, None, id="none")])
def test_walkthrough_runs_and_every_line_has_a_note(tmp_path, title, exercise):
    walk = exercise["walkthrough"]
    program = _program(exercise)
    lines = program.splitlines()
    for number, text in enumerate(lines, 1):
        if text.strip() and not text.strip().startswith("#"):
            assert number in walk["notes"], f"line {number} has no note: {text!r}"
    assert all(1 <= n <= len(lines) for n in walk["notes"])
    if walk.get("run") is False:
        return

    cwd = os.getcwd()
    os.chdir(tmp_path)  # each recording starts with an empty folder, like the sandbox
    try:
        result = _tracer().record(program, walk.get("setup", ""), walk.get("stdin"))
    finally:
        os.chdir(cwd)

    assert result["steps"], "nothing was recorded"
    assert not result["truncated"]
    if walk.get("expect_error"):
        assert result["error"]["type"] == walk["expect_error"]
        return
    assert result["error"] is None, result["error"]
    expected = exercise.get("simulated_output")
    random_output = "random" in program or "secrets" in program
    if expected is not None and not walk.get("try_it") and not random_output:
        assert result["stdout"].strip() == str(expected).strip()


def test_steps_show_values_changing_and_function_calls():
    result = _tracer().record("def double(x):\n    return x * 2\n\ntotal = 0\nfor n in [1, 2]:\n    total += double(n)\n")
    events = [(s["line"], s["event"]) for s in result["steps"]]
    assert (2, "return") in events
    assert result["steps"][-1]["globals"]["total"] == "6"
    inside = next(s for s in result["steps"] if s["frames"])
    assert inside["frames"][0]["name"] == "double"


def test_generators_show_yield_steps():
    result = _tracer().record("def g():\n    yield 1\n    yield 2\n\nfor v in g():\n    pass\n")
    kinds = [s["event"] for s in result["steps"]]
    assert kinds.count("yield") == 2
    assert kinds.count("return") == 1


def test_endless_loop_stops_at_the_step_limit():
    result = _tracer().record("while True:\n    pass\n", max_steps=50)
    assert result["truncated"]
    assert len(result["steps"]) == 50


def test_errors_are_reported_on_the_right_line():
    result = _tracer().record("x = 1\ny = x / 0\n")
    assert result["error"] == {"type": "ZeroDivisionError", "message": "division by zero", "line": 2}
    assert result["steps"][-1]["event"] == "exception"


def test_input_is_answered_from_stdin_and_echoed():
    result = _tracer().record('name = input("Name: ")\nprint("Hi", name)\n', stdin=["Ada"])
    assert result["stdout"] == "Name: Ada\nHi Ada\n"
    assert "input" not in result["steps"][-1]["globals"]
