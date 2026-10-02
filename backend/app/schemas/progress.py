"""Learner check submissions and progress reset."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CheckSubmit(BaseModel):
    attempt: str = Field(default="", max_length=20000)
    output: str | None = Field(default=None, max_length=8000)
    hints_used: int = Field(default=0, ge=0, le=16)
    wpm: int | None = Field(default=None, ge=0, le=400)
    accuracy: int | None = Field(default=None, ge=0, le=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)


class ProgressResetIn(BaseModel):
    """Clear lesson Done state for a chosen slice of the learning path."""

    scope: Literal["all", "track", "level", "module", "lesson"]
    track_slug: str | None = Field(default=None, max_length=64)
    level: Literal["beginner", "intermediate", "advanced"] | None = None
    module_id: UUID | None = None
    lesson_id: UUID | None = None

    @model_validator(mode="after")
    def scope_fields_match(self) -> "ProgressResetIn":
        if self.scope == "all":
            return self
        if self.scope == "track":
            if not self.track_slug:
                raise ValueError("track_slug is required for track reset")
            return self
        if self.scope == "level":
            if not self.track_slug or not self.level:
                raise ValueError("track_slug and level are required for level reset")
            return self
        if self.scope == "module":
            if self.module_id is None:
                raise ValueError("module_id is required for module reset")
            return self
        if self.lesson_id is None:
            raise ValueError("lesson_id is required for lesson reset")
        return self
