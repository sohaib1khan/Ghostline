"""Anthropic, OpenAI, and Ollama. Settings choose which one runs."""

from app.services.ai import transport
from app.services.ai.base import parse_json_object, with_schema
from app.services.ai.config import AiConfig
from app.services.ai.errors import AiError

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class JsonProvider:
    def __init__(self, config: AiConfig) -> None:
        self.config = config

    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        text = await self.complete(system_prompt, with_schema(user_prompt, schema))
        return parse_json_object(text)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


def _text(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise AiError("The AI provider returned an empty response.", status_code=502)


class AnthropicProvider(JsonProvider):
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        body = await transport.post_json(
            ANTHROPIC_URL,
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload={
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=self.config.timeout_seconds,
        )
        blocks = body.get("content")
        if not isinstance(blocks, list):
            raise AiError("The AI provider returned an empty response.", status_code=502)
        parts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return _text("".join(part for part in parts if isinstance(part, str)))


class OpenAIProvider(JsonProvider):
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        body = await transport.post_json(
            OPENAI_URL,
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            payload={
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=self.config.timeout_seconds,
        )
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AiError("The AI provider returned an empty response.", status_code=502)
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            content = "".join(parts)
        return _text(content)


class OllamaProvider(JsonProvider):
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"content-type": "application/json"}
        if self.config.api_key:
            headers["authorization"] = f"Bearer {self.config.api_key}"
        body = await transport.post_json(
            f"{self.config.base_url}/api/chat",
            headers=headers,
            payload={
                "model": self.config.model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"num_predict": self.config.max_tokens},
            },
            timeout=self.config.timeout_seconds,
        )
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        return _text(content)


PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def build_provider(config: AiConfig) -> JsonProvider:
    return PROVIDERS[config.provider](config)
