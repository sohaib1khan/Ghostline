"""One interface for every AI provider."""

import json
import re
from typing import Protocol

from app.services.ai.errors import AiError


class AiProvider(Protocol):
    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        """Return one JSON object. Callers validate it."""


def with_schema(user_prompt: str, schema: dict) -> str:
    encoded = json.dumps(schema, separators=(",", ":"))
    return f"{user_prompt}\n\nRespond with one JSON object that matches this schema:\n{encoded}"


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AiError("The model did not return JSON.", status_code=422)
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AiError("The model did not return valid JSON.", status_code=422) from exc
    if not isinstance(value, dict):
        raise AiError("The model did not return a JSON object.", status_code=422)
    return value
