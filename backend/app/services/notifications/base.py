"""Shared types for notification providers.

Every provider implements ``send(config, message)``. New providers register
in ``registry.SENDERS``.
"""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


class DeliveryError(Exception):
    """A send failed. The message must not contain secrets."""


@dataclass(frozen=True)
class Outbound:
    event: str
    title: str
    body: str
    recipient: str | None


class Provider(Protocol):
    async def __call__(self, config: dict, message: Outbound) -> None:
        """Deliver one message. Raise DeliveryError without secrets."""


def clean_http_url(value: str) -> str:
    """Accept http(s) URLs without embedded usernames or passwords."""
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("Put credentials in the secret field, not the URL")
    if len(candidate) > 500:
        raise ValueError("URL is too long")
    return candidate
