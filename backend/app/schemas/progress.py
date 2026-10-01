"""Learner check submissions."""

from pydantic import BaseModel, Field


class CheckSubmit(BaseModel):
    attempt: str = Field(default="", max_length=20000)
    output: str | None = Field(default=None, max_length=8000)
    hints_used: int = Field(default=0, ge=0, le=16)
    wpm: int | None = Field(default=None, ge=0, le=400)
    accuracy: int | None = Field(default=None, ge=0, le=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
