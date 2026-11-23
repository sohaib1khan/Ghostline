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


def test_walkthrough_round_trips_recorded_fields() -> None:
    data = ExerciseData.model_validate(
        {
            "type": "recall",
            "prompt": "Inc a counter",
            "code": "func (c *Counter) Inc() {\n\tc.n++\n}\n",
            "check": {
                "mode": "answers",
                "accepted_answers": ["func (c *Counter) Inc() {\n\tc.n++\n}\n"],
            },
            "walkthrough": {
                "given": "type Counter struct {\n\tn int\n}\n",
                "try_it": "c := Counter{}\nc.Inc()\nfmt.Println(c.n)\n",
                "args": ["ada"],
                "stdin": ["1"],
                "files": {"notes.txt": "hi\n"},
                "stdout": "1\n",
                "stderr": "",
                "exit_code": 0,
                "nondeterministic": False,
                "source_sha": None,
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
                        "line": 5,
                        "event": "end",
                        "globals": {"c": "{n:1}"},
                        "frames": [],
                        "stdout_len": 2,
                        "stderr_len": 0,
                    },
                ],
                "notes": {
                    1: "Pointer receiver.",
                    2: "Bump.",
                    3: "Try it.",
                    4: "Call.",
                    5: "Print.",
                },
            },
        }
    )
    # Fill source_sha after program is known.
    program, _ = build_walkthrough_program(data.model_dump())
    from app.services.walkthrough import program_sha

    dumped = data.model_dump()
    dumped["walkthrough"]["source_sha"] = program_sha(program)
    again = ExerciseData.model_validate(dumped)
    assert again.walkthrough is not None
    assert again.walkthrough.given.startswith("type Counter")
    assert again.walkthrough.steps[-1].event == "end"
    payload = serialize_walkthrough(dumped, track_slug="go")
    assert payload["recorded"] is True
    assert payload["stale"] is False
    assert payload["args"] == ["ada"]
