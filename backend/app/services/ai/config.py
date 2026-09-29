"""Saved AI settings. The API key lives in a separate encrypted row."""

from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.crypto import SecretError
from app.services.ai.errors import AiError
from app.services.settings_store import delete_setting, get_setting, set_setting

AI_CONFIG_KEY = "ai_config"
AI_KEY_SETTING = "ai_api_key"
PROVIDERS = ("anthropic", "openai", "ollama")
KEY_PROVIDERS = frozenset({"anthropic", "openai"})
# Link-local cloud metadata. An Ollama URL should not point here.
BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})


class AiConfigIn(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=120)
    base_url: str = Field(default="", max_length=300)
    max_tokens: int = Field(default=4096, ge=256, le=8192)
    timeout_seconds: int = Field(default=45, ge=5, le=120)
    enabled: bool = False
    api_key: str = Field(default="", max_length=500)
    clear_api_key: bool = False

    @field_validator("provider")
    @classmethod
    def known_provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in PROVIDERS:
            raise ValueError("Choose Anthropic, OpenAI, or Ollama")
        return cleaned

    @field_validator("model", "base_url", "api_key")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def url_ok(cls, value: str) -> str:
        if not value:
            return ""
        return clean_base_url(value)


@dataclass(frozen=True)
class AiConfig:
    provider: str
    model: str
    base_url: str
    max_tokens: int
    timeout_seconds: int
    enabled: bool
    api_key: str

    def public(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
            "api_key_set": bool(self.api_key),
        }


def clean_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Base URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("Base URL cannot include a username or password")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Base URL must be the server root, without a path")
    if host in BLOCKED_HOSTS:
        raise ValueError("That host cannot be used as an AI base URL")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _default() -> AiConfig:
    return AiConfig(
        provider="anthropic",
        model="",
        base_url="",
        max_tokens=4096,
        timeout_seconds=45,
        enabled=False,
        api_key="",
    )


def _from_stored(stored: object, api_key: str) -> AiConfig:
    if not isinstance(stored, dict):
        config = _default()
        return AiConfig(
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
            enabled=config.enabled,
            api_key=api_key,
        )
    provider = stored.get("provider")
    if provider not in PROVIDERS:
        provider = "anthropic"
    model = stored.get("model") if isinstance(stored.get("model"), str) else ""
    base_url = stored.get("base_url") if isinstance(stored.get("base_url"), str) else ""
    max_tokens = stored.get("max_tokens")
    timeout_seconds = stored.get("timeout_seconds")
    if not isinstance(max_tokens, int) or not 256 <= max_tokens <= 8192:
        max_tokens = 4096
    if not isinstance(timeout_seconds, int) or not 5 <= timeout_seconds <= 120:
        timeout_seconds = 45
    return AiConfig(
        provider=provider,
        model=model.strip()[:120],
        base_url=base_url.strip()[:300],
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        enabled=bool(stored.get("enabled")),
        api_key=api_key,
    )


async def load_config(session: AsyncSession) -> AiConfig:
    stored = await get_setting(session, AI_CONFIG_KEY)
    try:
        secret = await get_setting(session, AI_KEY_SETTING)
    except SecretError:
        secret = None
    api_key = secret if isinstance(secret, str) else ""
    return _from_stored(stored, api_key)


async def save_config(
    session: AsyncSession,
    payload: AiConfigIn,
) -> AiConfig:
    current = await load_config(session)
    if payload.clear_api_key:
        api_key = ""
    elif payload.api_key:
        api_key = payload.api_key
    else:
        api_key = current.api_key
    if payload.enabled and payload.provider in KEY_PROVIDERS and not api_key:
        raise AiError("Add an API key before turning this provider on.")
    if payload.enabled and payload.provider == "ollama" and not payload.base_url:
        raise AiError("Add the Ollama base URL before turning it on.")
    stored = {
        "provider": payload.provider,
        "model": payload.model,
        "base_url": payload.base_url,
        "max_tokens": payload.max_tokens,
        "timeout_seconds": payload.timeout_seconds,
        "enabled": payload.enabled,
    }
    await set_setting(session, AI_CONFIG_KEY, stored, is_secret=False)
    try:
        if api_key:
            await set_setting(session, AI_KEY_SETTING, api_key, is_secret=True)
        elif current.api_key:
            await delete_setting(session, AI_KEY_SETTING)
    except SecretError as exc:
        raise AiError("APP_ENCRYPTION_KEY cannot encrypt the API key.", status_code=500) from exc
    return AiConfig(api_key=api_key, **stored)


def require_ready(config: AiConfig, *, require_enabled: bool) -> None:
    if require_enabled and not config.enabled:
        raise AiError("Turn AI on in Admin → AI before generating a draft.")
    if not config.model:
        raise AiError("Save a model name.")
    if config.provider in KEY_PROVIDERS and not config.api_key:
        raise AiError("Save an API key for this provider.")
    if config.provider == "ollama" and not config.base_url:
        raise AiError("Save the Ollama base URL.")
