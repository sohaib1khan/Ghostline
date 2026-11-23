"""JavaScript (and peers) get Go-style notes-only step-through without NEWFEATURE YAML."""

from app.services.walkthrough import (
    has_walkthrough_payload,
    serialize_walkthrough,
    synthetic_walkthrough,
)


def _js_trace() -> dict:
    return {
        "type": "trace",
        "prompt": "Log hello",
        "code": 'console.log("hello")',
        "tokens": [{"match": "console.log", "explain": "Writes a line to the console."}],
        "check": {"mode": "answers", "accepted_answers": ['console.log("hello")']},
    }


def test_javascript_synthetic_walkthrough_from_tokens() -> None:
    synth = synthetic_walkthrough(_js_trace(), "javascript")
    assert synth is not None
    assert synth["run"] is False
    assert 1 in synth["notes"]
    assert "console" in synth["notes"][1].lower() or "Watch" in synth["notes"][1]
    assert has_walkthrough_payload(_js_trace(), "javascript") is True


def test_javascript_serialize_marks_synthetic_path() -> None:
    payload = serialize_walkthrough(_js_trace(), track_slug="javascript")
    assert payload is not None
    assert payload["track_slug"] == "javascript"
    assert payload["recorded"] is False
    assert payload["run"] is False
    assert payload["notes"][1]


def test_python_does_not_synthesize() -> None:
    assert synthetic_walkthrough(_js_trace(), "python") is None
    assert has_walkthrough_payload(_js_trace(), "python") is False


def test_sql_and_bash_also_synthesize() -> None:
    data = {
        "code": "SELECT 1;",
        "tokens": [{"match": "SELECT", "explain": "Pick columns."}],
        "check": {"accepted_answers": ["SELECT 1;"]},
    }
    assert synthetic_walkthrough(data, "sql") is not None
    bash = {"code": "ls", "tokens": [], "check": {"accepted_answers": ["ls"]}}
    assert synthetic_walkthrough(bash, "bash") is not None
