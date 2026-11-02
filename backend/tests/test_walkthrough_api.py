"""Walkthrough schema round-trip and payload helpers."""

from app.schemas.content import ExerciseData, WalkthroughIn
from app.services.walkthrough import build_walkthrough_program, serialize_walkthrough


def test_walkthrough_schema_accepts_notes_and_stdin() -> None:
    walk = WalkthroughIn.model_validate(
        {
            "setup": "words = ['owl']",
            "stdin": ["Ada"],
            "try_it": "print(words)",
            "run": True,
            "notes": {1: "Start here.", "2": "Next line."},
        }
    )
    assert walk.notes[1].startswith("Start")
    assert walk.notes[2].startswith("Next")
    assert walk.stdin == ["Ada"]


def test_exercise_data_round_trips_walkthrough() -> None:
    data = ExerciseData.model_validate(
        {
            "type": "trace",
            "prompt": "Type the loop",
            "code": "total = 0\nfor n in [1, 2]:\n    total += n\n",
            "check": {"mode": "answers", "accepted_answers": ["total = 0\nfor n in [1, 2]:\n    total += n\n"]},
            "walkthrough": {
                "setup": "",
                "try_it": "",
                "notes": {1: "Start the counter.", 2: "Each round.", 3: "Add n."},
            },
        }
    )
    dumped = data.model_dump()
    again = ExerciseData.model_validate(dumped)
    assert again.walkthrough is not None
    assert again.walkthrough.notes[1] == "Start the counter."


def test_build_program_appends_try_it() -> None:
    program, source_lines = build_walkthrough_program(
        {
            "code": "def double(x):\n    return x * 2\n",
            "walkthrough": {"try_it": "print(double(5))"},
        }
    )
    assert source_lines == 2
    assert program.endswith("print(double(5))")


def test_serialize_walkthrough_payload() -> None:
    payload = serialize_walkthrough(
        {
            "code": "print(1)\n",
            "walkthrough": {
                "setup": "x = 1",
                "stdin": [],
                "run": True,
                "notes": {1: "Print one."},
            },
        }
    )
    assert payload is not None
    assert payload["program"].startswith("print(1)")
    assert payload["notes"][1] == "Print one."
