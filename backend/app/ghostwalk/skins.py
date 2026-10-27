"""Convert Ghostwalk language skins into Python hero API code for server tests."""

from __future__ import annotations

import re

SNAKES = (
    "turn_left",
    "turn_right",
    "pick_up",
    "at_goal",
    "is_blocked",
    "on_gem",
    "on_soil",
    "crops_held",
    "read_sign",
    "harvest",
    "plant",
    "water",
    "move",
)


def _to_pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


def _strip_line_comments(code: str, patterns: list[str]) -> str:
    out_lines = []
    for line in code.splitlines():
        current = line
        for pattern in patterns:
            current = re.sub(pattern, "", current)
        out_lines.append(current)
    return "\n".join(out_lines)


def _map_pascal_calls(text: str) -> str:
    out = text
    for snake in SNAKES:
        pascal = _to_pascal(snake)
        out = re.sub(rf"hero\.{pascal}\s*\(\s*\)", f"hero.{snake}()", out)
    return out


def skin_to_python(language: str, code: str) -> str:
    """Best-effort transpile of language-flavored hero code into Python."""
    lang = (language or "python").lower()
    text = str(code or "")
    if lang == "python":
        return text

    if lang == "javascript":
        text = _strip_line_comments(text, [r"//.*$"])
        text = re.sub(
            r"for\s*\(\s*(?:let|var|const)\s+(\w+)\s*=\s*0;\s*\1\s*<\s*(\d+);\s*\1\+\+\s*\)\s*\{",
            r"for _ in range(\2):",
            text,
        )
        text = text.replace("{", "").replace("}", "")
        text = re.sub(r";\s*$", "", text, flags=re.M)
        return text

    if lang == "bash":
        text = _strip_line_comments(text, [r"#(?!!).*$"])
        text = re.sub(
            r"\bhero_([a-z_]+)\s*\(\s*\)",
            lambda m: f"hero.{m.group(1).lower()}()",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\bfor\s+_\s+in\s+\$\(seq\s+(\d+)\)\s*;\s*do",
            r"for _ in range(\1):",
            text,
            flags=re.I,
        )
        text = re.sub(r"\bdone\b", "", text)
        return text

    if lang == "go":
        text = _strip_line_comments(text, [r"//.*$"])
        text = _map_pascal_calls(text)
        text = re.sub(
            r"\bfor\s+(\w+)\s*:=\s*0;\s*\1\s*<\s*(\d+);\s*\1\+\+\s*\{",
            r"for _ in range(\2):",
            text,
        )
        text = text.replace("{", "").replace("}", "")
        return text

    if lang in {"java", "csharp"}:
        text = _strip_line_comments(text, [r"//.*$"])
        text = _map_pascal_calls(text)
        text = re.sub(
            r"\bfor\s*\(\s*int\s+(\w+)\s*=\s*0;\s*\1\s*<\s*(\d+);\s*\1\+\+\s*\)\s*\{?",
            r"for _ in range(\2):",
            text,
        )
        text = text.replace("{", "").replace("}", "")
        text = re.sub(r";\s*$", "", text, flags=re.M)
        return text

    if lang == "sql":
        text = _strip_line_comments(text, [r"--.*$"])

        def _call(match: re.Match[str]) -> str:
            return f"hero.{match.group(1).lower()}()"

        text = re.sub(r"\b(?:CALL|SELECT)\s+([a-z_]+)\s*\(\s*\)\s*;?", _call, text, flags=re.I)
        return text

    return text
