"""String checks for exercises. Learner code is never executed here."""

import re
import threading
from dataclasses import dataclass

# DECISION: Python's re engine can lock up on nested repetition. Patterns are
# rejected when a repeated group has no required literal, and every match is
# abandoned if it runs longer than MATCH_TIMEOUT_SECONDS.
MAX_PATTERN_LENGTH = 200
MAX_ATTEMPT_LENGTH = 20000
MATCH_TIMEOUT_SECONDS = 0.1
QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ab": '"',
        "\u00bb": '"',
    }
)
SHORTHAND = set("sSdDwWAZbB")


class PatternError(ValueError):
    """The regex is invalid or unsafe to run."""


@dataclass(frozen=True)
class CheckOutcome:
    passed: bool
    hint: str | None
    failed_kind: str | None


def validate_pattern(pattern: str) -> None:
    if not isinstance(pattern, str) or not pattern.strip():
        raise PatternError("A regex rule needs a pattern")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise PatternError("That regex is too long")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise PatternError("That regex is not valid") from exc
    if _ambiguous_repeat(pattern):
        raise PatternError("That regex can take too long. Simplify the repetition.")
    for probe in ("", "a" * 40, "a" * 40 + "!"):
        if _match(pattern, probe) is None:
            raise PatternError("That regex can take too long. Simplify the repetition.")


def normalize_text(value: str, options: dict) -> str:
    text = value.translate(QUOTE_MAP) if options.get("equivalent_quotes") else value
    if options.get("trim", True):
        text = text.strip()
    if options.get("collapse_whitespace"):
        text = re.sub(r"\s+", " ", text)
    if not options.get("case_sensitive", True):
        text = text.casefold()
    return text


def check_attempt(data: dict, attempt: str, output: str | None = None) -> CheckOutcome:
    if len(attempt) > MAX_ATTEMPT_LENGTH:
        return CheckOutcome(False, "That answer is too long.", None)
    check = data.get("check") or {}
    options = check.get("normalize") or {}
    mode = check.get("mode") or "either"
    answers = [normalize_text(str(item), options) for item in check.get("accepted_answers") or []]
    rules = list(check.get("rules") or [])
    normalized = normalize_text(attempt, options)
    answers_match = bool(answers) and normalized in answers
    soft_miss = "Not quite — open a hint and try again."
    if mode == "answers":
        if answers_match:
            return CheckOutcome(True, None, None)
        return CheckOutcome(False, _fallback_hint(rules, soft_miss), None)
    rule_outcome = _rules(rules, normalized, output, options, data)
    if mode == "rules":
        return rule_outcome
    if answers_match or rule_outcome.passed:
        return CheckOutcome(True, None, None)
    if rules:
        return rule_outcome
    return CheckOutcome(False, soft_miss, None)


def _fallback_hint(rules: list[dict], default: str) -> str:
    for rule in rules:
        hint = str(rule.get("hint") or "").strip()
        if hint:
            return hint
    return default


def _rules(
    rules: list[dict],
    attempt: str,
    output: str | None,
    options: dict,
    data: dict,
) -> CheckOutcome:
    if not rules:
        return CheckOutcome(False, "Add at least one rule.", None)
    for rule in rules:
        kind = str(rule.get("kind") or "")
        ok, hint = _one_rule(kind, rule, attempt, output, options, data)
        if not ok:
            return CheckOutcome(False, hint or "Not quite.", kind or None)
    return CheckOutcome(True, None, None)


def _one_rule(
    kind: str,
    rule: dict,
    attempt: str,
    output: str | None,
    options: dict,
    data: dict,
) -> tuple[bool, str]:
    hint = str(rule.get("hint") or "").strip()
    if kind == "exact":
        value = rule.get("value")
        if isinstance(value, str) and value != "":
            return normalize_text(value, options) == attempt, hint
        answers = data.get("check", {}).get("accepted_answers") or []
        normalized = [normalize_text(str(item), options) for item in answers]
        return bool(normalized) and attempt in normalized, hint
    if kind == "must_contain":
        return _contains(attempt, rule.get("value"), options), hint
    if kind == "must_not_contain":
        return not _contains(attempt, rule.get("value"), options), hint
    if kind == "must_contain_any":
        values = rule.get("values") or []
        return any(_contains(attempt, item, options) for item in values), hint
    if kind == "must_contain_all":
        values = rule.get("values") or []
        return bool(values) and all(_contains(attempt, item, options) for item in values), hint
    if kind == "regex":
        pattern = str(rule.get("pattern") or "")
        matched = _match(pattern, attempt)
        if matched is None:
            return False, "That pattern took too long to check."
        return matched, hint
    if kind == "line_count":
        count = 0 if attempt == "" else len(attempt.splitlines())
        minimum = rule.get("minimum")
        maximum = rule.get("maximum")
        if minimum is not None and count < int(minimum):
            return False, hint
        if maximum is not None and count > int(maximum):
            return False, hint
        return True, hint
    if kind == "output_equals":
        expected = data.get("expected_output")
        if expected is None or output is None:
            return False, hint or "There is no program output to compare."
        return normalize_text(output, options) == normalize_text(str(expected), options), hint
    return False, hint or "Unknown rule."


def _contains(attempt: str, value: object, options: dict) -> bool:
    if not isinstance(value, str) or value == "":
        return False
    return normalize_text(value, options) in attempt


def _match(pattern: str, text: str) -> bool | None:
    if len(text) > MAX_ATTEMPT_LENGTH:
        text = text[:MAX_ATTEMPT_LENGTH]
    box: dict[str, bool] = {}

    def run() -> None:
        box["ok"] = re.fullmatch(pattern, text) is not None

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(MATCH_TIMEOUT_SECONDS)
    if worker.is_alive():
        return None
    return box.get("ok", False)


def _ambiguous_repeat(pattern: str) -> bool:
    """True when a repeated group can match one span in more than one way."""
    simplified = _simplify(pattern)
    groups = _groups(simplified)
    for body, quantified in groups:
        if not quantified:
            continue
        if not re.search(r"[*+{]", body):
            continue
        for alternative in _split_alts(body):
            if not _has_required_literal(alternative):
                return True
    return False


def _simplify(pattern: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            nxt = pattern[index + 1] if index + 1 < len(pattern) else ""
            out.append("C" if nxt in SHORTHAND else "L")
            index += 2
            continue
        if char == "[":
            index += 1
            while index < len(pattern) and pattern[index] != "]":
                index += 2 if pattern[index] == "\\" else 1
            index += 1
            out.append("C")
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _groups(text: str) -> list[tuple[str, bool]]:
    found: list[tuple[str, bool]] = []
    stack: list[int] = []
    for index, char in enumerate(text):
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            start = stack.pop()
            nxt = text[index + 1] if index + 1 < len(text) else ""
            found.append((_group_body(text[start + 1 : index]), nxt in "*+{"))
    return found


def _split_alts(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "|" and depth == 0:
            parts.append(body[start:index])
            start = index + 1
    parts.append(body[start:])
    return parts


def _group_body(body: str) -> str:
    if body.startswith("?:"):
        return body[2:]
    if body.startswith("?P<"):
        end = body.find(">")
        return body[end + 1 :] if end != -1 else body
    return body


def _has_required_literal(alternative: str) -> bool:
    meta = set("^$*.+?{}()|C")
    index = 0
    while index < len(alternative):
        char = alternative[index]
        nxt = alternative[index + 1] if index + 1 < len(alternative) else ""
        if char not in meta and nxt not in "*+?{":
            return True
        index += 1
    return False
