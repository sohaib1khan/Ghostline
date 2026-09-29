"""Check engine rules, normalization, and regex safety."""

import pytest
from app.services.check_engine import (
    PatternError,
    check_attempt,
    normalize_text,
    validate_pattern,
)

NORMALIZE = {
    "collapse_whitespace": True,
    "trim": True,
    "equivalent_quotes": False,
    "case_sensitive": True,
}


def exercise(rules, answers=None, mode="either", expected=None, **extra):
    data = {
        "type": "recall",
        "prompt": "Try it",
        "runtime": "none",
        "check": {
            "mode": mode,
            "accepted_answers": answers or [],
            "normalize": dict(NORMALIZE),
            "rules": rules,
        },
        "expected_output": expected,
    }
    data.update(extra)
    return data


def test_each_rule_kind() -> None:
    cases = [
        ([{"kind": "exact", "value": "ls -la"}], "ls -la", True),
        ([{"kind": "must_contain", "value": "ls", "hint": "Use ls"}], "pwd", False),
        ([{"kind": "must_not_contain", "value": "rm", "hint": "Do not delete"}], "rm -rf", False),
        ([{"kind": "must_contain_any", "values": ["-a", "-la"]}], "ls -la", True),
        (
            [{"kind": "must_contain_all", "values": ["ls", "-a"], "hint": "Need both"}],
            "ls -l",
            False,
        ),
        ([{"kind": "regex", "pattern": r"^ls( -[la]+)+$"}], "ls -la", True),
        ([{"kind": "line_count", "minimum": 2, "maximum": 3}], "one\ntwo", True),
        ([{"kind": "output_equals", "hint": "Check the output"}], "ignored", False),
    ]
    for rules, attempt, passed in cases:
        output = "nope" if rules[0]["kind"] == "output_equals" else None
        expected = "hello" if rules[0]["kind"] == "output_equals" else None
        data = exercise(rules, expected=expected)
        if rules[0]["kind"] == "line_count":
            data["check"]["normalize"]["collapse_whitespace"] = False
        outcome = check_attempt(data, attempt, output)
        assert outcome.passed is passed
        if not passed:
            assert outcome.hint


def test_output_equals_passes() -> None:
    outcome = check_attempt(
        exercise([{"kind": "output_equals"}], expected="hello"),
        "anything",
        "hello",
    )
    assert outcome.passed is True


def test_modes_and_normalization() -> None:
    data = exercise(
        [{"kind": "must_contain", "value": "ls", "hint": "Use ls"}],
        answers=["ls -la"],
        mode="either",
    )
    data["check"]["normalize"]["collapse_whitespace"] = True
    assert check_attempt(data, "  ls   -la ").passed is True
    data["check"]["mode"] = "rules"
    assert check_attempt(data, "pwd").passed is False
    assert check_attempt(data, "pwd").hint == "Use ls"
    data["check"]["mode"] = "answers"
    assert check_attempt(data, "ls").passed is False
    data["check"]["normalize"]["case_sensitive"] = False
    data["check"]["mode"] = "answers"
    assert check_attempt(data, "LS -LA").passed is True


def test_equivalent_quotes() -> None:
    options = dict(NORMALIZE)
    options["equivalent_quotes"] = True
    assert normalize_text("“hello”", options) == '"hello"'


def test_first_failing_rule_wins() -> None:
    outcome = check_attempt(
        exercise(
            [
                {"kind": "must_contain", "value": "ls", "hint": "first"},
                {"kind": "must_contain", "value": "-a", "hint": "second"},
            ],
            mode="rules",
        ),
        "pwd",
    )
    assert outcome.hint == "first"
    assert outcome.failed_kind == "must_contain"


def test_safe_pattern_is_accepted_and_nested_repeat_is_rejected() -> None:
    validate_pattern(r"^ls( -[la]+)+$")
    with pytest.raises(PatternError):
        validate_pattern("(a+)+")
    with pytest.raises(PatternError):
        validate_pattern("(" + "a" * 201)


def test_empty_rules_in_rules_mode_fail() -> None:
    outcome = check_attempt(exercise([], mode="rules"), "ls")
    assert outcome.passed is False
