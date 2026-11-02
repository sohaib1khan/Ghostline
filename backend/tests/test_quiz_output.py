"""Run every seeded kind:output quiz and check the printed answer."""

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

SEED = Path(__file__).resolve().parents[1] / "app" / "seed" / "lessons"
ERROR_Q = re.compile(r"what happens when this runs", re.I)


def _output_quizzes():
    for path in sorted(SEED.glob("*.yaml")):
        track = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for module in track.get("modules") or []:
            for lesson in module.get("lessons") or []:
                for exercise in lesson.get("exercises") or []:
                    for index, item in enumerate(exercise.get("quiz") or []):
                        if item.get("kind") != "output":
                            continue
                        yield pytest.param(
                            path.stem,
                            lesson.get("title"),
                            exercise.get("order"),
                            index,
                            item,
                            id=f"{path.stem}:{lesson.get('title')}:{exercise.get('order')}:q{index}",
                        )


_SEEDED = list(_output_quizzes())


def _run_code(code: str, tmp_path: Path) -> str:
    script = tmp_path / "quiz_snippet.py"
    script.write_text(textwrap.dedent(code).rstrip() + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0:
        return (result.stdout or "").rstrip("\n")
    err = (result.stderr or "").strip()
    last = err.splitlines()[-1] if err else "Error"
    # Match "ErrorType: message" style answers used in the YAML.
    if ": " in last:
        name, _, message = last.partition(": ")
        if name.endswith("Error") or name.endswith("Exception") or name.endswith("Warning"):
            return f"{name}: {message}".rstrip()
    match = re.search(r"^([A-Za-z_][A-Za-z0-9_]*)[:\s]", last)
    if match:
        return f"{match.group(1)}: {last.partition(':')[2].lstrip()}".rstrip()
    return last


@pytest.mark.skipif(
    not _SEEDED,
    reason="No seeded output quizzes yet — import python.yaml via Studio",
)
@pytest.mark.parametrize(
    ("track", "lesson", "order", "index", "item"),
    _SEEDED or [pytest.param(None, None, None, None, None, id="none")],
)
def test_output_quiz_matches_answer(tmp_path, track, lesson, order, index, item):
    code = item.get("code") or ""
    assert code.strip(), "output quiz needs code"
    got = _run_code(code, tmp_path)
    expected = str(item.get("answer") or "")
    if ERROR_Q.search(str(item.get("q") or "")):
        # Allow either full "Type: message" or a type-only answer.
        assert got == expected or got.startswith(f"{expected}:") or expected in got, (
            f"{track}/{lesson}#{order} q{index}: expected {expected!r}, got {got!r}"
        )
        return
    assert got == expected, f"{track}/{lesson}#{order} q{index}: expected {expected!r}, got {got!r}"
