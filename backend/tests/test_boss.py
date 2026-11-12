"""Boss hints schema, credit math, safe messages, and seed YAML hygiene."""

from pathlib import Path

import pytest
import yaml
from app.schemas.content import ExerciseData
from app.services.boss import (
    boss_hint_ladder,
    boss_safe_message,
    item_credit,
)
from pydantic import ValidationError

SEED = Path(__file__).resolve().parents[1] / "app" / "seed" / "lessons" / "python.yaml"


def _exercise(**extra):
    body = {
        "type": "recall",
        "prompt": "Define settings",
        "code": "",
        "check": {
            "mode": "answers",
            "accepted_answers": ["def settings(**opts):\n    return len(opts)"],
        },
    }
    body.update(extra)
    return body


def test_boss_hints_round_trip() -> None:
    data = ExerciseData.model_validate(
        _exercise(
            boss_hints=[
                'From the lesson "Keyword bundles": **kwargs collects named values.',
                "You need:\n- the keyword def\n- def settings(...):\n- the operator **",
                "The shape:\n```python\ndef ___(**___):\n    return ___(___)\n```",
            ]
        )
    )
    dumped = data.model_dump()
    again = ExerciseData.model_validate(dumped)
    assert len(again.boss_hints) == 3
    assert "___" in again.boss_hints[2]


def test_boss_hints_reject_too_long() -> None:
    with pytest.raises(ValidationError):
        ExerciseData.model_validate(_exercise(boss_hints=["x" * 4001]))


def test_boss_hints_fallback_ladder() -> None:
    ladder = boss_hint_ladder(
        {
            "hints": [
                "Think about kwargs.",
                "You need:\n- def\n- **",
            ]
        },
        lesson_title="Keyword bundles",
        lesson_summary="**kwargs collects named values.",
    )
    assert ladder[0].startswith('From the lesson "Keyword bundles"')
    assert ladder[1].startswith("You need:")


def test_credit_math() -> None:
    assert item_credit(hint_level=0, tries=1, passed=True, revealed=False) == 1.0
    assert item_credit(hint_level=3, tries=1, passed=True, revealed=False) == 0.5
    assert item_credit(hint_level=1, tries=2, passed=True, revealed=False) == 0.45
    assert item_credit(hint_level=0, tries=1, passed=False, revealed=True) == 0.0
    assert item_credit(hint_level=2, tries=2, passed=False, revealed=False) == 0.0


def test_boss_safe_message_never_leaks_answer() -> None:
    expected = "def settings(**opts):\n    return len(opts)"
    msg = boss_safe_message("def settings(opts):\n    return len(opts)", expected)
    assert "settings(**opts)" not in msg
    assert "return len(opts)" not in msg
    assert "Line" in msg
    indent = boss_safe_message("def settings(**opts):\nreturn len(opts)", expected)
    assert "indent" in indent.lower()


def test_seed_boss_hints_are_safe() -> None:
    if not SEED.exists():
        pytest.skip("python seed missing")
    doc = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    answers: list[str] = []
    hints: list[tuple[str, str]] = []
    for module in doc.get("modules") or []:
        for lesson in module.get("lessons") or []:
            for exercise in lesson.get("exercises") or []:
                check = exercise.get("check") or {}
                for answer in check.get("accepted_answers") or []:
                    text = str(answer).strip()
                    if len(text) >= 8:
                        answers.append(text)
                for step in exercise.get("boss_hints") or []:
                    hints.append((str(step), str(exercise.get("prompt") or "")))
    for step, _prompt in hints:
        for answer in answers:
            if len(answer) >= 8 and answer in step:
                raise AssertionError(f"boss_hints contains accepted answer: {answer!r}")
        # Shape steps (thirdish) should blank identifiers with ___
        if "```" in step or "___" in step:
            assert step.count("___") >= 2, f"shape step needs ≥2 blanks: {step[:80]!r}"
