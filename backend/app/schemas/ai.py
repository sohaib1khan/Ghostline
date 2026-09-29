"""Admin inputs for an AI lesson draft."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DraftLessonIn(BaseModel):
    module_id: UUID
    topic: str = Field(min_length=1, max_length=200)
    difficulty: str
    exercise_count: int = Field(ge=1, le=6)
    exercise_types: list[str] = Field(min_length=1, max_length=4)

    @field_validator("topic", "difficulty")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("difficulty")
    @classmethod
    def known_difficulty(cls, value: str) -> str:
        if value not in {"beginner", "intermediate"}:
            raise ValueError("Difficulty must be beginner or intermediate")
        return value

    @field_validator("exercise_types")
    @classmethod
    def known_types(cls, value: list[str]) -> list[str]:
        allowed = {"trace", "fill", "recall", "challenge"}
        if any(item not in allowed for item in value):
            raise ValueError("Exercise type must be trace, fill, recall, or challenge")
        if len(set(value)) != len(value):
            raise ValueError("Choose each exercise type once")
        return value
