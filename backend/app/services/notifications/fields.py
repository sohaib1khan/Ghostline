"""Which settings each provider stores, and which of them are secrets."""

import re

from email_validator import EmailNotValidError, validate_email

from app.models.notification import PROVIDERS
from app.services.notifications.base import clean_http_url

EVENTS = (
    "user.signup",
    "user.approved",
    "user.rejected",
    "admin.login",
    "content.published",
)
EMAIL_PROVIDERS = frozenset({"resend", "smtp"})
# These go to the learner. Other events use the channel's admin address.
USER_EMAIL_EVENTS = frozenset({"user.approved", "user.rejected"})

# kind: secret, optional_secret, email, text, optional_text, port, security, url, topic, priority
FIELD_KINDS: dict[str, dict[str, str]] = {
    "resend": {"api_key": "secret", "from_email": "email", "to_email": "email"},
    "smtp": {
        "host": "text",
        "port": "port",
        "security": "security",
        "username": "optional_text",
        "password": "optional_secret",
        "from_email": "email",
        "to_email": "email",
    },
    "gotify": {"base_url": "url", "token": "secret", "priority": "priority"},
    "slack": {"webhook_url": "secret_url"},
    "discord": {"webhook_url": "secret_url"},
    "ntfy": {"base_url": "url", "topic": "topic", "token": "optional_secret"},
    "webhook": {"url": "url", "bearer_token": "optional_secret"},
}

SECRET_KINDS = frozenset({"secret", "optional_secret", "secret_url"})


class ConfigError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def secret_names(provider: str) -> set[str]:
    return {name for name, kind in FIELD_KINDS[provider].items() if kind in SECRET_KINDS}


def _email(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{label} is required")
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ConfigError(f"{label} is not a valid email") from exc


def _text(value: object, label: str, *, required: bool, limit: int = 200) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ConfigError(f"{label} is required")
        return ""
    if not isinstance(value, str):
        raise ConfigError(f"{label} is required")
    cleaned = value.strip()
    if len(cleaned) > limit:
        raise ConfigError(f"{label} is too long")
    return cleaned


def _one(kind: str, key: str, value: object) -> object:
    label = key.replace("_", " ")
    if kind == "email":
        return _email(value, label)
    if kind == "text":
        return _text(value, label, required=True)
    if kind == "optional_text":
        return _text(value, label, required=False)
    if kind in {"secret", "optional_secret"}:
        required = kind == "secret"
        return _text(value, label, required=required, limit=500)
    if kind == "secret_url":
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{label} is required")
        try:
            return clean_http_url(value)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    if kind == "url":
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{label} is required")
        try:
            return clean_http_url(value).rstrip("/")
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    if kind == "port":
        try:
            port = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError("port must be a number") from exc
        if port < 1 or port > 65535:
            raise ConfigError("port must be between 1 and 65535")
        return port
    if kind == "security":
        choice = str(value or "starttls").strip().lower()
        if choice not in {"starttls", "ssl", "none"}:
            raise ConfigError("security must be starttls, ssl, or none")
        return choice
    if kind == "topic":
        topic = _text(value, "topic", required=True)
        if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", topic) is None:
            raise ConfigError("topic may only use letters, numbers, dashes, and underscores")
        return topic
    if kind == "priority":
        if value in (None, ""):
            return 5
        try:
            priority = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError("priority must be a number") from exc
        if priority < 0 or priority > 10:
            raise ConfigError("priority must be between 0 and 10")
        return priority
    raise ConfigError("Unknown setting")


def validate_config(provider: str, raw: dict) -> dict:
    if provider not in PROVIDERS:
        raise ConfigError("Unknown provider")
    kinds = FIELD_KINDS[provider]
    unknown = set(raw) - set(kinds)
    if unknown:
        raise ConfigError("Unknown setting")
    cleaned: dict = {}
    for key, kind in kinds.items():
        cleaned[key] = _one(kind, key, raw.get(key))
    return cleaned


def public_config(provider: str, config: dict) -> tuple[dict, dict[str, bool]]:
    """Return non-secret values and which secrets are stored."""
    visible: dict = {}
    secrets: dict[str, bool] = {}
    for key, kind in FIELD_KINDS[provider].items():
        if kind in SECRET_KINDS:
            secrets[key] = bool(config.get(key))
        else:
            visible[key] = config.get(key, "")
    return visible, secrets
