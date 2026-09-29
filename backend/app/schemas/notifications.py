"""Admin notification channel payloads."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["resend", "smtp", "gotify", "slack", "discord", "ntfy", "webhook"]
EventName = Literal[
    "user.signup",
    "user.approved",
    "user.rejected",
    "admin.login",
    "content.published",
]


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: ProviderName
    events: list[EventName] = Field(default_factory=list, max_length=5)
    is_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @field_validator("events")
    @classmethod
    def unique_events(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen


class ChannelOut(BaseModel):
    id: UUID
    name: str
    provider: str
    events: list[str]
    is_enabled: bool
    config: dict[str, Any]
    secrets: dict[str, bool]
    last_test_at: datetime | None
    last_test_ok: bool | None


class ChannelListOut(BaseModel):
    channels: list[ChannelOut]
    email_channel_ready: bool


class TestOut(BaseModel):
    ok: bool
    detail: str
