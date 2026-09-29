"""Turn a model response into a draft lesson. Invalid output is not saved."""

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.user import User
from app.schemas.ai import DraftLessonIn
from app.schemas.content import ExerciseData
from app.services.ai.config import load_config
from app.services.ai.errors import AiError
from app.services.ai.registry import generate_json
from app.services.audit import write_audit
from app.services.content_store import _lesson_node, _next_position

SYSTEM_PROMPT = (
    "You write original lessons for Ghostline, a typing-first tutor for Bash, "
    "Python, Go, and JavaScript. Produce original explanations. Do not copy text "
    "from websites or documentation. Use only real commands, flags, and functions "
    "for the track. Keep the wording beginner-friendly. Respond with one JSON "
    "object and no other text. Do not add keys that are not in the schema."
)


class AiLessonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=300)
    body_markdown: str = Field(min_length=1, max_length=20000)
    exercises: list[ExerciseData] = Field(min_length=1, max_length=8)


def _user_prompt(track_name: str, track_slug: str, payload: DraftLessonIn) -> str:
    kinds = ", ".join(payload.exercise_types)
    return (
        f"Track: {track_name} ({track_slug})\n"
        f"Topic: {payload.topic}\n"
        f"Difficulty: {payload.difficulty}\n"
        f"Write exactly {payload.exercise_count} exercises.\n"
        f"Each exercise type must be one of: {kinds}.\n"
        "A trace exercise needs code for the learner to retype.\n"
        "A fill exercise needs code and at least one blank.\n"
        "A challenge exercise needs a time limit in seconds.\n"
        "Every exercise needs a prompt and a check with at least one accepted answer."
    )


def _format_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"]) or "draft"
    message = str(first.get("msg") or "invalid")
    return f"The draft did not match the lesson format ({location}: {message})."


def _checked(payload: DraftLessonIn, raw: dict) -> AiLessonDraft:
    try:
        draft = AiLessonDraft.model_validate(raw)
    except ValidationError as exc:
        raise AiError(_format_error(exc), status_code=422) from exc
    if len(draft.exercises) != payload.exercise_count:
        raise AiError(
            "The draft did not include the requested number of exercises.",
            status_code=422,
        )
    allowed = set(payload.exercise_types)
    for item in draft.exercises:
        if item.type not in allowed:
            raise AiError(
                f"The draft used {item.type}, which was not requested.",
                status_code=422,
            )
    return draft


async def _audit_failure(
    session: AsyncSession,
    *,
    actor: User,
    payload: DraftLessonIn,
    detail: str,
    ip: str | None,
) -> None:
    config = await load_config(session)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="ai.draft_rejected",
        target_type="lesson",
        details={
            "provider": config.provider,
            "model": config.model,
            "topic": payload.topic,
            "error": detail[:300],
        },
        ip=ip,
    )
    await session.commit()


async def draft_lesson(
    session: AsyncSession,
    *,
    actor: User,
    payload: DraftLessonIn,
    ip: str | None,
) -> dict:
    module = await session.get(Module, payload.module_id, options=[selectinload(Module.track)])
    if module is None:
        raise AiError("Module not found", status_code=404)
    try:
        raw = await generate_json(
            session,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=_user_prompt(module.track.name, module.track.slug, payload),
            schema=AiLessonDraft.model_json_schema(),
            require_enabled=True,
        )
        draft = _checked(payload, raw)
    except AiError as exc:
        detail = exc.detail
        if "Nothing was saved" not in detail:
            detail = f"{detail} Nothing was saved."
        await _audit_failure(session, actor=actor, payload=payload, detail=detail, ip=ip)
        raise AiError(detail, status_code=exc.status_code) from exc

    # DECISION: a generated lesson is always a draft. Publishing stays a separate
    # admin action after review.
    position = await _next_position(session, Lesson.position, Lesson.module_id == module.id)
    lesson = Lesson(
        module_id=module.id,
        title=draft.title.strip(),
        summary=draft.summary.strip(),
        body_markdown=draft.body_markdown,
        position=position,
        status="draft",
        is_demo=False,
        source_type="ai_generated",
        source_attribution="AI draft. Review before publishing.",
        source_url="",
        license_note="",
        created_by=actor.id,
        updated_by=actor.id,
    )
    session.add(lesson)
    await session.flush()
    for index, item in enumerate(draft.exercises, start=1):
        session.add(
            Exercise(
                lesson_id=lesson.id,
                position=index,
                type=item.type,
                data=item.model_dump(),
                status="draft",
            )
        )
    config = await load_config(session)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="ai.draft",
        target_type="lesson",
        target_id=str(lesson.id),
        details={
            "provider": config.provider,
            "model": config.model,
            "topic": payload.topic,
            "exercise_count": len(draft.exercises),
            "status": "draft",
        },
        ip=ip,
    )
    await session.commit()
    await session.refresh(lesson, attribute_names=["exercises"])
    return _lesson_node(lesson, summary=False)


async def test_connection(
    session: AsyncSession,
    *,
    actor: User,
    ip: str | None,
) -> dict:
    config = await load_config(session)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    try:
        await generate_json(
            session,
            system_prompt="Reply with JSON only.",
            user_prompt='Return {"ok": true}.',
            schema=schema,
            require_enabled=False,
        )
    except AiError:
        await write_audit(
            session,
            actor_user_id=actor.id,
            action="ai.test",
            target_type="ai",
            details={"provider": config.provider, "model": config.model, "ok": False},
            ip=ip,
        )
        await session.commit()
        raise
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="ai.test",
        target_type="ai",
        details={"provider": config.provider, "model": config.model, "ok": True},
        ip=ip,
    )
    await session.commit()
    return {"ok": True, "detail": "Connected."}
