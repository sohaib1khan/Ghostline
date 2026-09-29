"""Admin content payloads. Exercise data matches docs/content-format.md."""

from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.check_engine import PatternError, validate_pattern

ExerciseType = Literal["trace", "fill", "recall", "challenge"]
LessonStatus = Literal["draft", "review", "published"]
ModuleStatus = Literal["draft", "published"]
SourceType = Literal["original", "adapted", "ai_generated"]
CheckMode = Literal["answers", "rules", "either"]
RuntimeName = Literal["none", "browser_js", "pyodide"]
RuleKind = Literal[
    "exact",
    "must_contain",
    "must_not_contain",
    "must_contain_any",
    "must_contain_all",
    "regex",
    "line_count",
    "output_equals",
]


class TokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match: str = Field(min_length=1, max_length=80)
    explain: str = Field(min_length=1, max_length=300)


class BlankIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=1, le=200)
    placeholder: str = Field(default="__", max_length=20)


class NormalizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collapse_whitespace: bool = True
    trim: bool = True
    equivalent_quotes: bool = False
    case_sensitive: bool = True


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RuleKind
    value: str | None = Field(default=None, max_length=4000)
    values: list[str] = Field(default_factory=list, max_length=20)
    pattern: str | None = Field(default=None, max_length=200)
    hint: str = Field(default="", max_length=500)
    minimum: int | None = Field(default=None, ge=0, le=500)
    maximum: int | None = Field(default=None, ge=0, le=500)

    @field_validator("values")
    @classmethod
    def short_values(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 20000:
                raise ValueError("A rule value is too long")
        return value

    @model_validator(mode="after")
    def kind_has_fields(self) -> "RuleIn":
        if self.kind == "regex":
            try:
                validate_pattern(self.pattern or "")
            except PatternError as exc:
                raise ValueError(str(exc)) from exc
        elif self.kind in {"must_contain", "must_not_contain"} and not (self.value or "").strip():
            raise ValueError(f"{self.kind} needs a value")
        elif self.kind in {"must_contain_any", "must_contain_all"} and not self.values:
            raise ValueError(f"{self.kind} needs values")
        elif self.kind == "line_count" and self.minimum is None and self.maximum is None:
            raise ValueError("line_count needs a minimum or a maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("line_count minimum is above the maximum")
        return self


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: CheckMode = "either"
    accepted_answers: list[str] = Field(default_factory=list, max_length=20)
    normalize: NormalizeIn = Field(default_factory=NormalizeIn)
    rules: list[RuleIn] = Field(default_factory=list, max_length=20)

    @field_validator("accepted_answers")
    @classmethod
    def short_answers(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 20000:
                raise ValueError("An accepted answer is too long")
        return value

    @model_validator(mode="after")
    def mode_has_something(self) -> "CheckIn":
        if self.mode == "answers" and not self.accepted_answers:
            raise ValueError("Add an accepted answer")
        if self.mode == "rules" and not self.rules:
            raise ValueError("Add at least one rule")
        if self.mode == "either" and not self.accepted_answers and not self.rules:
            raise ValueError("Add an accepted answer or a rule")
        return self


class ExerciseData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: ExerciseType
    prompt: str = Field(min_length=1, max_length=4000)
    runtime: RuntimeName = "none"
    code: str = Field(default="", max_length=20000)
    tokens: list[TokenIn] = Field(default_factory=list, max_length=80)
    blanks: list[BlankIn] = Field(default_factory=list, max_length=40)
    check: CheckIn
    hints: list[str] = Field(default_factory=list, max_length=16)
    simulated_output: str | None = Field(default=None, max_length=8000)
    expected_output: str | None = Field(default=None, max_length=8000)
    xp: int = Field(default=10, ge=0, le=1000)
    time_limit_seconds: int | None = Field(default=None, ge=1, le=3600)

    @field_validator("hints")
    @classmethod
    def short_hints(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 800:
                raise ValueError("A hint is too long")
        return value

    @model_validator(mode="after")
    def type_fields(self) -> "ExerciseData":
        if self.type == "fill" and not self.blanks:
            raise ValueError("A fill exercise needs at least one blank")
        if self.type == "trace" and not self.code.strip():
            raise ValueError("A trace exercise needs code to type over")
        # DECISION: a challenge may omit the timer for longer guided scripts.
        # The admin editor still defaults new short challenges to 60 seconds.
        if self.runtime != "none" and self.expected_output is None:
            raise ValueError("A browser runtime needs expected output")
        return self


def clean_source_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Source URL must start with http:// or https://")
    if len(cleaned) > 500:
        raise ValueError("Source URL is too long")
    return cleaned


class ModuleIn(BaseModel):
    track_id: UUID
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    status: ModuleStatus = "draft"

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ModulePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    status: ModuleStatus | None = None


class LessonIn(BaseModel):
    module_id: UUID
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=300)
    body_markdown: str = Field(default="", max_length=20000)
    status: Literal["draft", "review"] = "draft"
    is_demo: bool = False
    source_type: SourceType = "original"
    source_attribution: str = Field(default="", max_length=200)
    source_url: str = Field(default="", max_length=500)
    license_note: str = Field(default="", max_length=200)

    @field_validator("source_url")
    @classmethod
    def url_ok(cls, value: str) -> str:
        return clean_source_url(value)


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=300)
    body_markdown: str | None = Field(default=None, max_length=20000)
    status: Literal["draft", "review"] | None = None
    is_demo: bool | None = None
    source_type: SourceType | None = None
    source_attribution: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    license_note: str | None = Field(default=None, max_length=200)
    module_id: UUID | None = None

    @field_validator("source_url")
    @classmethod
    def url_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_source_url(value)


class ExerciseIn(BaseModel):
    lesson_id: UUID
    status: Literal["draft", "published"] = "draft"
    data: ExerciseData


class ExercisePatch(BaseModel):
    status: Literal["draft", "published"] | None = None
    data: ExerciseData | None = None
    lesson_id: UUID | None = None


class ReorderIn(BaseModel):
    kind: Literal["module", "lesson", "exercise"]
    parent_id: UUID
    ids: list[UUID] = Field(min_length=1, max_length=200)


class TestCheckIn(BaseModel):
    data: ExerciseData
    attempt: str = Field(default="", max_length=20000)
    output: str | None = Field(default=None, max_length=8000)


class ParseExerciseIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    format: Literal["json", "yaml"] = "json"


class ImportIn(BaseModel):
    document: str = Field(min_length=1, max_length=4_000_000)
    dry_run: bool = True
    # DECISION: extend is the default so a downloaded file can be edited and
    # uploaded again without deleting lessons or the progress on them.
    mode: Literal["extend", "replace"] = "extend"
    # When true, every module, lesson, and exercise in the file is stored as
    # published so Learn and Games can use it immediately.
    publish: bool = False


class TrackPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=300)
    is_active: bool | None = None


def exercise_document(data: ExerciseData, *, status: str, position: int) -> dict[str, Any]:
    body = data.model_dump()
    body["status"] = status
    body["order"] = position
    return body
