"""Admin user management payloads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.auth import _clean_name

Role = Literal["admin", "learner"]
Status = Literal["pending", "approved", "rejected", "disabled"]


def _clean_slugs(value: list[str]) -> list[str]:
    cleaned: list[str] = []
    for slug in value:
        item = slug.strip().lower()
        if not item or len(item) > 40 or not item.replace("-", "").isalnum():
            raise ValueError("Invalid track")
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


class TrackSlugsIn(BaseModel):
    track_slugs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("track_slugs")
    @classmethod
    def clean_slugs(cls, value: list[str]) -> list[str]:
        return _clean_slugs(value)


class AdminCreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    role: Role = "learner"
    track_slugs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("track_slugs")
    @classmethod
    def clean_slugs(cls, value: list[str]) -> list[str]:
        return _clean_slugs(value)


class UserPatchIn(BaseModel):
    role: Role | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def something_changes(self) -> "UserPatchIn":
        if self.role is None and self.status is None:
            raise ValueError("Nothing to change")
        return self


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=12, max_length=200)


class AdminUserOut(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    track_slugs: list[str]
    created_at: datetime
    last_login_at: datetime | None


class TrackOut(BaseModel):
    slug: str
    name: str
    description: str
    icon: str
    color: str
    order: int
