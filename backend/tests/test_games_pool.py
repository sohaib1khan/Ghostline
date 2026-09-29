"""Pure pool rules for games — no database required."""

from types import SimpleNamespace

from app.services.games import _public_round, _suitable, break_code


def _exercise(type_: str, **data) -> SimpleNamespace:
    return SimpleNamespace(type=type_, data=data)


def test_break_code_flips_last_alnum() -> None:
    assert break_code("SET") == "SEx"
    assert break_code("x") == "y"
    assert break_code("!!!") == "!!! "


def test_speed_drill_needs_trace_code() -> None:
    assert _suitable("speed_drill", _exercise("trace", code="ls"))
    assert not _suitable("speed_drill", _exercise("trace", code="   "))
    assert not _suitable("speed_drill", _exercise("fill", code="ls", blanks=[{"index": 1}]))


def test_bug_hunt_rejects_fill_and_unbroken() -> None:
    assert _suitable("bug_hunt", _exercise("trace", code="SELECT 1"))
    assert not _suitable("bug_hunt", _exercise("fill", code="SELECT 1", blanks=[{"index": 1}]))
    # Empty string cannot be broken into a different printable line for play.
    assert not _suitable("bug_hunt", _exercise("trace", code=""))


def test_fill_frenzy_requires_blanks() -> None:
    assert _suitable(
        "fill_frenzy",
        _exercise("fill", code="a b", blanks=[{"index": 1, "answer": "a"}]),
    )
    assert not _suitable("fill_frenzy", _exercise("fill", code="a b", blanks=[]))
    assert not _suitable("fill_frenzy", _exercise("trace", code="a b"))


def test_command_roulette_is_recall_or_challenge() -> None:
    assert _suitable("command_roulette", _exercise("recall", prompt="List files"))
    assert _suitable("command_roulette", _exercise("challenge", prompt="Write a loop"))
    assert not _suitable(
        "command_roulette",
        _exercise("fill", prompt="Fill me", code="a b", blanks=[{"index": 1}]),
    )
    assert not _suitable("command_roulette", _exercise("recall", prompt="  "))


def test_bug_hunt_public_round_hides_answer() -> None:
    lesson = SimpleNamespace(title="Ops", module=SimpleNamespace(track=SimpleNamespace(slug="sql")))
    exercise = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        type="trace",
        data={
            "prompt": "Type this",
            "code": "SELECT 1",
            "check": {"accepted_answers": ["SELECT 1"]},
            "tokens": [],
        },
        lesson=lesson,
    )
    body = _public_round("bug_hunt", exercise, pool_size=3)
    assert body["broken"] == "SELECT x"
    assert "code" not in body
    assert body["prompt"].startswith("One character")
    assert any("Do not copy" in hint for hint in body["hints"])
