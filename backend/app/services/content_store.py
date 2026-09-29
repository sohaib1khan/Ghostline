"""Create and edit modules, lessons, and exercises."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import ContentRevision, Exercise, Lesson, Module
from app.models.track import Track, UserTrackAccess
from app.models.user import User
from app.schemas.content import (
    ExerciseData,
    ExerciseIn,
    ExercisePatch,
    LessonIn,
    LessonPatch,
    ModuleIn,
    ModulePatch,
    TrackPatch,
)
from app.services.audit import write_audit
from app.services.check_engine import check_attempt
from app.services.notifications.dispatcher import dispatch_event


class ContentError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _lesson_options():
    return (
        selectinload(Lesson.exercises),
        selectinload(Lesson.module).selectinload(Module.track),
    )


async def content_tree(session: AsyncSession) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(Track)
                .options(
                    selectinload(Track.modules)
                    .selectinload(Module.lessons)
                    .selectinload(Lesson.exercises)
                )
                .order_by(Track.position, Track.slug)
            )
        ).all()
    )
    return [_track_node(track) for track in rows]


def _track_node(track: Track) -> dict:
    return {
        "id": track.id,
        "slug": track.slug,
        "name": track.name,
        "description": track.description,
        "is_active": track.is_active,
        "order": track.position,
        "modules": [_module_node(module) for module in track.modules],
    }


def _module_node(module: Module) -> dict:
    return {
        "id": module.id,
        "title": module.title,
        "description": module.description,
        "order": module.position,
        "status": module.status,
        "lessons": [_lesson_node(lesson, summary=True) for lesson in module.lessons],
    }


def _lesson_node(lesson: Lesson, *, summary: bool) -> dict:
    body = {
        "id": lesson.id,
        "title": lesson.title,
        "summary": lesson.summary,
        "order": lesson.position,
        "status": lesson.status,
        "is_demo": lesson.is_demo,
        "exercises": [
            {
                "id": item.id,
                "order": item.position,
                "type": item.type,
                "status": item.status,
                "prompt": (item.data or {}).get("prompt", ""),
            }
            for item in lesson.exercises
        ],
    }
    if summary:
        return body
    body.update(
        {
            "body_markdown": lesson.body_markdown,
            "source_type": lesson.source_type,
            "source_attribution": lesson.source_attribution,
            "source_url": lesson.source_url,
            "license_note": lesson.license_note,
            "module_id": lesson.module_id,
            "exercises": [_exercise_out(item) for item in lesson.exercises],
        }
    )
    return body


def _exercise_out(row: Exercise) -> dict:
    return {
        "id": row.id,
        "lesson_id": row.lesson_id,
        "order": row.position,
        "type": row.type,
        "status": row.status,
        "data": row.data,
    }


def _jsonable(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def learner_lesson(lesson: Lesson, exercises: list[Exercise] | None = None) -> dict:
    return {
        "id": lesson.id,
        "title": lesson.title,
        "summary": lesson.summary,
        "body_markdown": lesson.body_markdown,
        "status": lesson.status,
        "is_demo": lesson.is_demo,
        "source_type": lesson.source_type,
        "source_attribution": lesson.source_attribution,
        "source_url": lesson.source_url,
        "license_note": lesson.license_note,
        "track_slug": lesson.module.track.slug,
        "track_name": lesson.module.track.name,
        "module_title": lesson.module.title,
        "exercises": [
            _learner_exercise(item)
            for item in (lesson.exercises if exercises is None else exercises)
        ],
    }


def _practice_hints(exercise_type: str, data: dict) -> list[str]:
    """Author hints first; if none, build progressive guidance for fill/recall/challenge."""
    authored = [str(item).strip() for item in (data.get("hints") or []) if str(item).strip()]
    if authored:
        return authored[:16]
    check = data.get("check") or {}
    rule_hints = [
        str(rule.get("hint") or "").strip()
        for rule in (check.get("rules") or [])
        if str(rule.get("hint") or "").strip()
    ]
    if exercise_type == "fill":
        return _fill_hints(data, rule_hints)[:16]
    if exercise_type in {"recall", "challenge"}:
        generated = list(rule_hints)
        answers = [str(item) for item in (check.get("accepted_answers") or []) if str(item).strip()]
        if answers:
            sample = answers[0].strip()
            if sample and len(sample) <= 80:
                generated.append(f"It starts like this: {sample[: max(1, min(3, len(sample)))]}…")
                generated.append(f"One accepted shape is `{sample}`.")
        return generated[:16]
    return rule_hints[:16]


def _fill_hints(data: dict, rule_hints: list[str]) -> list[str]:
    code = str(data.get("code") or "")
    words = [part for part in code.strip().split() if part]
    answers = [
        str(item) for item in ((data.get("check") or {}).get("accepted_answers") or []) if str(item).strip()
    ]
    answer_words = [part for part in (answers[0] if answers else code).strip().split() if part]
    hints = list(rule_hints)
    blanks = list(data.get("blanks") or [])
    if not blanks and words:
        blanks = [{"index": 1}]
    for blank in blanks:
        try:
            index = int(blank.get("index") or 0)
        except (TypeError, ValueError):
            continue
        if index < 1 or index > len(answer_words):
            continue
        word = answer_words[index - 1]
        label = f"Blank {index}" if len(blanks) > 1 else "The blank"
        hints.append(f"{label} is where a key word goes — think about the prompt.")
        hints.append(f"{label} starts with “{word[0]}”.")
        if len(word) > 2:
            hints.append(f"{label} is {len(word)} characters long.")
        hints.append(f"{label} is `{word}`.")
    if not hints and words:
        hints.append("Fill each gap so the line matches the usual command.")
    # Dedupe while keeping order.
    seen: set[str] = set()
    unique: list[str] = []
    for hint in hints:
        if hint in seen:
            continue
        seen.add(hint)
        unique.append(hint)
    return unique


def _learner_exercise(row: Exercise) -> dict:
    data = row.data or {}
    # DECISION: recall and challenge hide the canonical code so the answer is
    # not in the page. Trace and fill need that code as the ghost text.
    code = data.get("code", "") if row.type in {"trace", "fill"} else ""
    return {
        "id": row.id,
        "order": row.position,
        "type": row.type,
        "prompt": data.get("prompt", ""),
        "runtime": data.get("runtime", "none"),
        "code": code,
        "tokens": data.get("tokens") or [],
        "blanks": data.get("blanks") or [],
        "hints": _practice_hints(row.type, data),
        "simulated_output": data.get("simulated_output"),
        "xp": data.get("xp", 0),
        "time_limit_seconds": data.get("time_limit_seconds"),
    }


async def update_track(
    session: AsyncSession,
    *,
    actor: User,
    track_id: uuid.UUID,
    patch: TrackPatch,
    ip: str | None,
) -> dict:
    track = await session.get(Track, track_id)
    if track is None:
        raise ContentError(404, "Track not found")
    if patch.name is not None:
        track.name = patch.name.strip()
    if patch.description is not None:
        track.description = patch.description.strip()
    if patch.is_active is not None:
        track.is_active = patch.is_active
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.track_update",
        target_type="track",
        target_id=str(track.id),
        details={"slug": track.slug, "is_active": track.is_active},
        ip=ip,
    )
    await session.commit()
    return {"id": track.id, "slug": track.slug, "name": track.name, "is_active": track.is_active}


async def create_module(
    session: AsyncSession, *, actor: User, payload: ModuleIn, ip: str | None
) -> dict:
    track = await session.get(Track, payload.track_id)
    if track is None:
        raise ContentError(404, "Track not found")
    position = await _next_position(session, Module.position, Module.track_id == track.id)
    row = Module(
        track_id=track.id,
        title=payload.title,
        description=payload.description,
        position=position,
        status=payload.status,
    )
    session.add(row)
    await session.flush()
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.module_create",
        target_type="module",
        target_id=str(row.id),
        details={"title": row.title, "track": track.slug},
        ip=ip,
    )
    await session.commit()
    await session.refresh(row, attribute_names=["lessons"])
    return _module_node(row)


async def update_module(
    session: AsyncSession,
    *,
    actor: User,
    module_id: uuid.UUID,
    patch: ModulePatch,
    ip: str | None,
) -> dict:
    row = await session.get(Module, module_id, options=[selectinload(Module.lessons)])
    if row is None:
        raise ContentError(404, "Module not found")
    if patch.title is not None:
        row.title = patch.title.strip()
    if patch.description is not None:
        row.description = patch.description.strip()
    if patch.status is not None:
        row.status = patch.status
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.module_update",
        target_type="module",
        target_id=str(row.id),
        details={"title": row.title, "status": row.status},
        ip=ip,
    )
    await session.commit()
    return _module_node(row)


async def delete_module(
    session: AsyncSession, *, actor: User, module_id: uuid.UUID, ip: str | None
) -> None:
    row = await session.get(Module, module_id)
    if row is None:
        raise ContentError(404, "Module not found")
    title = row.title
    await session.delete(row)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.delete",
        target_type="module",
        target_id=str(module_id),
        details={"title": title},
        ip=ip,
    )
    await session.commit()


async def create_lesson(
    session: AsyncSession, *, actor: User, payload: LessonIn, ip: str | None
) -> dict:
    module = await session.get(Module, payload.module_id)
    if module is None:
        raise ContentError(404, "Module not found")
    position = await _next_position(session, Lesson.position, Lesson.module_id == module.id)
    row = Lesson(
        module_id=module.id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        body_markdown=payload.body_markdown,
        position=position,
        status=payload.status,
        is_demo=payload.is_demo,
        source_type=payload.source_type,
        source_attribution=payload.source_attribution.strip(),
        source_url=payload.source_url,
        license_note=payload.license_note.strip(),
        created_by=actor.id,
        updated_by=actor.id,
    )
    session.add(row)
    await session.flush()
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.lesson_create",
        target_type="lesson",
        target_id=str(row.id),
        details={"title": row.title},
        ip=ip,
    )
    await session.commit()
    await session.refresh(row, attribute_names=["exercises"])
    return _lesson_node(row, summary=False)


async def get_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> dict:
    row = await _load_lesson(session, lesson_id)
    return _lesson_node(row, summary=False)


async def preview_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> dict:
    row = await _load_lesson(session, lesson_id)
    return learner_lesson(row)


async def update_lesson(
    session: AsyncSession,
    *,
    actor: User,
    lesson_id: uuid.UUID,
    patch: LessonPatch,
    ip: str | None,
) -> dict:
    row = await _load_lesson(session, lesson_id)
    # DECISION: editing a live lesson moves it back to review so learners keep
    # seeing the last published version until an admin publishes again.
    was_published = row.status == "published"
    if patch.module_id is not None and patch.module_id != row.module_id:
        module = await session.get(Module, patch.module_id)
        if module is None:
            raise ContentError(404, "Module not found")
        row.module_id = module.id
        row.position = await _next_position(session, Lesson.position, Lesson.module_id == module.id)
    for field in (
        "title",
        "summary",
        "body_markdown",
        "is_demo",
        "source_type",
        "source_attribution",
        "source_url",
        "license_note",
    ):
        value = getattr(patch, field)
        if value is not None:
            if isinstance(value, str) and field != "body_markdown":
                value = value.strip()
            setattr(row, field, value)
    if was_published:
        row.status = "review"
    elif patch.status is not None:
        row.status = patch.status
    row.updated_by = actor.id
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.lesson_update",
        target_type="lesson",
        target_id=str(row.id),
        details={"title": row.title, "status": row.status},
        ip=ip,
    )
    await session.commit()
    row = await _load_lesson(session, lesson_id)
    return _lesson_node(row, summary=False)


async def delete_lesson(
    session: AsyncSession, *, actor: User, lesson_id: uuid.UUID, ip: str | None
) -> None:
    row = await session.get(Lesson, lesson_id)
    if row is None:
        raise ContentError(404, "Lesson not found")
    title = row.title
    await session.delete(row)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.delete",
        target_type="lesson",
        target_id=str(lesson_id),
        details={"title": title},
        ip=ip,
    )
    await session.commit()


async def publish_lesson(
    session: AsyncSession, *, actor: User, lesson_id: uuid.UUID, ip: str | None
) -> dict:
    row = await _load_lesson(session, lesson_id)
    if not row.exercises:
        raise ContentError(400, "Add an exercise before publishing")
    row.status = "published"
    row.module.status = "published"
    for exercise in row.exercises:
        exercise.status = "published"
    row.updated_by = actor.id
    snapshot = _jsonable(_lesson_node(row, summary=False))
    session.add(
        ContentRevision(
            entity_type="lesson",
            entity_id=row.id,
            snapshot=snapshot,
            edited_by=actor.id,
        )
    )
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.publish",
        target_type="lesson",
        target_id=str(row.id),
        details={"title": row.title, "track": row.module.track.slug},
        ip=ip,
    )
    title = row.title
    slug = row.module.track.slug
    await session.commit()
    await dispatch_event("content.published", {"title": title, "track": slug})
    return await get_lesson(session, lesson_id)


async def publish_track(
    session: AsyncSession, *, actor: User, track_id: uuid.UUID, ip: str | None
) -> dict:
    """Publish every draft/review lesson on a track that already has exercises."""
    track = await session.get(Track, track_id)
    if track is None:
        raise ContentError(404, "Track not found")
    rows = list(
        (
            await session.scalars(
                select(Lesson)
                .join(Module, Lesson.module_id == Module.id)
                .where(Module.track_id == track.id, Lesson.status != "published")
                .options(selectinload(Lesson.exercises), selectinload(Lesson.module))
                .order_by(Module.position, Lesson.position)
            )
        ).all()
    )
    published = 0
    skipped = 0
    for row in rows:
        if not row.exercises:
            skipped += 1
            continue
        row.status = "published"
        row.module.status = "published"
        for exercise in row.exercises:
            exercise.status = "published"
        row.updated_by = actor.id
        published += 1
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.publish_track",
        target_type="track",
        target_id=str(track.id),
        details={"slug": track.slug, "published": published, "skipped_empty": skipped},
        ip=ip,
    )
    await session.commit()
    if published:
        await dispatch_event(
            "content.published",
            {"title": f"{published} lessons on {track.name}", "track": track.slug},
        )
    return {"slug": track.slug, "published": published, "skipped_empty": skipped}


async def create_exercise(
    session: AsyncSession, *, actor: User, payload: ExerciseIn, ip: str | None
) -> dict:
    lesson = await session.get(Lesson, payload.lesson_id)
    if lesson is None:
        raise ContentError(404, "Lesson not found")
    position = await _next_position(session, Exercise.position, Exercise.lesson_id == lesson.id)
    row = Exercise(
        lesson_id=lesson.id,
        position=position,
        type=payload.data.type,
        data=payload.data.model_dump(),
        status=payload.status,
    )
    session.add(row)
    _unpublish_if_live(lesson)
    await session.flush()
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.exercise_create",
        target_type="exercise",
        target_id=str(row.id),
        details={"type": row.type, "lesson": lesson.title},
        ip=ip,
    )
    await session.commit()
    return _exercise_out(row)


async def update_exercise(
    session: AsyncSession,
    *,
    actor: User,
    exercise_id: uuid.UUID,
    patch: ExercisePatch,
    ip: str | None,
) -> dict:
    row = await session.get(Exercise, exercise_id, options=[selectinload(Exercise.lesson)])
    if row is None:
        raise ContentError(404, "Exercise not found")
    if patch.lesson_id is not None and patch.lesson_id != row.lesson_id:
        lesson = await session.get(Lesson, patch.lesson_id)
        if lesson is None:
            raise ContentError(404, "Lesson not found")
        row.lesson_id = lesson.id
        row.position = await _next_position(
            session, Exercise.position, Exercise.lesson_id == lesson.id
        )
        row.lesson = lesson
    if patch.data is not None:
        row.data = patch.data.model_dump()
        row.type = patch.data.type
    if patch.status is not None:
        row.status = patch.status
    _unpublish_if_live(row.lesson)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.exercise_update",
        target_type="exercise",
        target_id=str(row.id),
        details={"type": row.type},
        ip=ip,
    )
    await session.commit()
    return _exercise_out(row)


async def delete_exercise(
    session: AsyncSession, *, actor: User, exercise_id: uuid.UUID, ip: str | None
) -> None:
    row = await session.get(Exercise, exercise_id, options=[selectinload(Exercise.lesson)])
    if row is None:
        raise ContentError(404, "Exercise not found")
    _unpublish_if_live(row.lesson)
    await session.delete(row)
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.delete",
        target_type="exercise",
        target_id=str(exercise_id),
        details={"type": row.type},
        ip=ip,
    )
    await session.commit()


async def reorder(
    session: AsyncSession,
    *,
    actor: User,
    kind: str,
    parent_id: uuid.UUID,
    ids: list[uuid.UUID],
    ip: str | None,
) -> None:
    if kind == "module":
        parent = await session.get(Track, parent_id)
        model = Module
        parent_column = Module.track_id
    elif kind == "lesson":
        parent = await session.get(Module, parent_id)
        model = Lesson
        parent_column = Lesson.module_id
    else:
        parent = await session.get(Lesson, parent_id)
        model = Exercise
        parent_column = Exercise.lesson_id
    if parent is None:
        raise ContentError(404, "Parent not found")
    rows = list((await session.scalars(select(model).where(parent_column == parent_id))).all())
    if set(ids) != {row.id for row in rows} or len(ids) != len(rows):
        raise ContentError(400, "The order must include every item once")
    by_id = {row.id: row for row in rows}
    for index, item_id in enumerate(ids, start=1):
        by_id[item_id].position = index
    await write_audit(
        session,
        actor_user_id=actor.id,
        action="content.reorder",
        target_type=kind,
        target_id=str(parent_id),
        details={"count": len(ids)},
        ip=ip,
    )
    await session.commit()


def run_test_check(data: ExerciseData, attempt: str, output: str | None) -> dict:
    outcome = check_attempt(data.model_dump(), attempt, output)
    return {"passed": outcome.passed, "hint": outcome.hint, "failed_kind": outcome.failed_kind}


async def outline_for(session: AsyncSession, track: Track) -> dict:
    modules = list(
        (
            await session.scalars(
                select(Module)
                .where(Module.track_id == track.id, Module.status == "published")
                .options(selectinload(Module.lessons))
                .order_by(Module.position)
            )
        ).all()
    )
    leveled = _assign_module_levels(modules)
    return {
        "slug": track.slug,
        "name": track.name,
        "description": track.description,
        "path": [
            {
                "id": "beginner",
                "label": "Beginner",
                "blurb": "Basics first — commands and syntax until they feel familiar.",
            },
            {
                "id": "intermediate",
                "label": "Intermediate",
                "blurb": "More programming — combine ideas with guided practice.",
            },
            {
                "id": "advanced",
                "label": "Advanced",
                "blurb": "Put it together — longer scripts and small projects.",
            },
        ],
        "modules": leveled,
    }


def _level_from_text(title: str, description: str) -> str | None:
    del description  # Titles alone pin Daily scripts / Projects; core modules use order.
    title_l = title.strip().lower()
    if title_l == "projects":
        return "advanced"
    if title_l == "daily scripts":
        return "intermediate"
    return None


def _assign_module_levels(modules: list[Module]) -> list[dict]:
    """Map modules onto beginner → intermediate → advanced for the learn path."""
    # DECISION: special module titles are fixed bands. Remaining modules split
    # by order so early lessons stay basic and later ones introduce more.
    fixed: dict[int, str] = {}
    core_indexes: list[int] = []
    for index, module in enumerate(modules):
        tagged = _level_from_text(module.title, module.description or "")
        if tagged:
            fixed[index] = tagged
        else:
            core_indexes.append(index)
    beginner_slots = max(1, (len(core_indexes) + 1) // 2) if core_indexes else 0
    levels_by_index: dict[int, str] = dict(fixed)
    for offset, index in enumerate(core_indexes):
        levels_by_index[index] = "beginner" if offset < beginner_slots else "intermediate"

    labels = {
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
    }
    payload = []
    for index, module in enumerate(modules):
        level = levels_by_index.get(index, "beginner")
        payload.append(
            {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "level": level,
                "level_label": labels[level],
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "summary": lesson.summary,
                        "is_demo": lesson.is_demo,
                    }
                    for lesson in module.lessons
                    if lesson.status == "published"
                ],
            }
        )
    return payload


PROJECTS_MODULE_TITLE = "Projects"


async def projects_for_user(session: AsyncSession, user: User) -> dict:
    """Curated mini-projects: published lessons under modules titled Projects."""
    from app.services.tracks import list_visible_tracks

    tracks = await list_visible_tracks(session, user)
    if not tracks:
        return {"projects": []}
    modules = list(
        (
            await session.scalars(
                select(Module)
                .where(
                    Module.track_id.in_([track.id for track in tracks]),
                    Module.status == "published",
                    Module.title == PROJECTS_MODULE_TITLE,
                )
                .options(
                    selectinload(Module.lessons),
                    selectinload(Module.track),
                )
                .order_by(Module.track_id, Module.position)
            )
        ).all()
    )
    projects = []
    for module in modules:
        for lesson in module.lessons:
            if lesson.status != "published":
                continue
            projects.append(
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "summary": lesson.summary,
                    "track_slug": module.track.slug,
                    "track_name": module.track.name,
                    "module_id": module.id,
                    "level": "advanced",
                    "level_label": "Advanced",
                }
            )
    return {"projects": projects}


async def lesson_for_learner(session: AsyncSession, user: User, lesson_id: uuid.UUID) -> dict:
    row = await _load_lesson(session, lesson_id)
    if (
        row.status != "published"
        or row.module.status != "published"
        or not row.module.track.is_active
    ):
        raise ContentError(404, "Lesson not found")
    if user.role != "admin":
        access = await session.scalar(
            select(UserTrackAccess.id).where(
                UserTrackAccess.user_id == user.id,
                UserTrackAccess.track_id == row.module.track.id,
            )
        )
        if access is None:
            raise ContentError(403, "You do not have access to this track")
    siblings = list(
        (
            await session.scalars(
                select(Module)
                .where(Module.track_id == row.module.track_id, Module.status == "published")
                .options(selectinload(Module.lessons))
                .order_by(Module.position)
            )
        ).all()
    )
    leveled = _assign_module_levels(siblings)
    band = next((item for item in leveled if item["id"] == row.module_id), None)
    visible = [item for item in row.exercises if item.status == "published"]
    payload = learner_lesson(row, visible)
    payload["level"] = band["level"] if band else "beginner"
    payload["level_label"] = band["level_label"] if band else "Beginner"
    payload["next_lesson"] = _next_lesson_in_path(leveled, row.id)
    return payload


def _next_lesson_in_path(leveled: list[dict], current_id: uuid.UUID) -> dict | None:
    """Next published lesson on the beginner → intermediate → advanced path."""
    ordered: list[dict] = []
    for level in ("beginner", "intermediate", "advanced"):
        for module in leveled:
            if module.get("level") != level:
                continue
            for lesson in module.get("lessons") or []:
                ordered.append(lesson)
    seen = False
    for lesson in ordered:
        if seen:
            return {"id": lesson["id"], "title": lesson["title"]}
        if lesson["id"] == current_id:
            seen = True
    return None


async def _load_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> Lesson:
    row = await session.scalar(
        select(Lesson).where(Lesson.id == lesson_id).options(*_lesson_options())
    )
    if row is None:
        raise ContentError(404, "Lesson not found")
    return row


async def _next_position(session: AsyncSession, column, condition) -> int:
    current = await session.scalar(select(func.max(column)).where(condition))
    return int(current or 0) + 1


def _unpublish_if_live(lesson: Lesson) -> None:
    if lesson.status == "published":
        lesson.status = "review"
