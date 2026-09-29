"""YAML and JSON import/export for lessons and tracks."""

import json
import uuid
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Exercise, Lesson, Module
from app.models.track import Track
from app.schemas.content import ExerciseData, SourceType, clean_source_url
from app.services.audit import write_audit
from app.services.content_store import ContentError

LessonStatus = Literal["draft", "review", "published"]
ItemStatus = Literal["draft", "published"]


class ImportedExercise(ExerciseData):
    status: ItemStatus = "published"
    order: int | None = None

    @field_validator("order")
    @classmethod
    def order_starts_at_one(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("order starts at 1")
        return value


class ImportedLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=300)
    body_markdown: str = Field(default="", max_length=20000)
    status: LessonStatus = "draft"
    is_demo: bool = False
    source_type: SourceType = "original"
    source_attribution: str = Field(default="", max_length=200)
    source_url: str = Field(default="", max_length=500)
    license_note: str = Field(default="", max_length=200)
    exercises: list[ImportedExercise] = Field(default_factory=list, max_length=40)

    def cleaned_url(self) -> str:
        return clean_source_url(self.source_url)


class ImportedModule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    status: ItemStatus = "published"
    lessons: list[ImportedLesson] = Field(default_factory=list, max_length=40)


class ImportedTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=40)
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    modules: list[ImportedModule] = Field(default_factory=list, max_length=60)


class ImportedCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracks: list[ImportedTrack] = Field(min_length=1, max_length=20)


def parse_document(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise ContentError(400, "The document is empty")
    try:
        if stripped.startswith("{"):
            loaded = json.loads(stripped)
        else:
            # DECISION: safe_load only. YAML tags that construct Python objects
            # are rejected, so an import cannot run code.
            loaded = yaml.safe_load(stripped)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContentError(400, "The document is not valid YAML or JSON") from exc
    if not isinstance(loaded, dict):
        raise ContentError(400, "The document must be an object")
    return loaded


def parse_exercise_text(text: str, fmt: str) -> dict:
    stripped = text.strip()
    try:
        if fmt == "json":
            loaded = json.loads(stripped)
        else:
            loaded = yaml.safe_load(stripped)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContentError(400, "That exercise text is not valid") from exc
    try:
        data = ExerciseData.model_validate(loaded)
    except ValidationError as exc:
        raise ContentError(400, _validation_message(exc)) from exc
    return data.model_dump()


def _dump(document: dict, fmt: str) -> tuple[str, str]:
    if fmt == "json":
        return json.dumps(document, indent=2), "application/json"
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True), "application/yaml"


async def export_track(session: AsyncSession, slug: str, fmt: str) -> tuple[str, str]:
    track = await _track(session, slug)
    return _dump(_track_document(track), fmt)


async def export_catalog(session: AsyncSession, fmt: str) -> tuple[str, str]:
    tracks = list(
        (
            await session.scalars(
                select(Track)
                .order_by(Track.position, Track.slug)
                .options(
                    selectinload(Track.modules)
                    .selectinload(Module.lessons)
                    .selectinload(Lesson.exercises)
                )
            )
        ).all()
    )
    return _dump({"tracks": [_track_document(track) for track in tracks]}, fmt)


async def export_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, fmt: str
) -> tuple[str, str, str]:
    lesson = await session.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.exercises),
            selectinload(Lesson.module).selectinload(Module.track),
        )
    )
    if lesson is None:
        raise ContentError(404, "Lesson not found")
    module = lesson.module
    track = module.track
    document = {
        "slug": track.slug,
        "name": track.name,
        "description": track.description,
        "modules": [
            {
                "title": module.title,
                "description": module.description,
                "status": module.status,
                "lessons": [_lesson_document(lesson)],
            }
        ],
    }
    body, media = _dump(document, fmt)
    filename = f"{_filename_piece(track.slug)}-{_filename_piece(lesson.title)}.yaml"
    if fmt == "json":
        filename = filename.removesuffix(".yaml") + ".json"
    return body, media, filename


def _filename_piece(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts)[:40] or "lesson"


async def import_track(
    session: AsyncSession,
    *,
    actor_id,
    document: str,
    dry_run: bool,
    ip: str | None,
    commit: bool = True,
    mode: str = "replace",
    publish: bool = False,
) -> dict:
    # Seed calls this to load a full starter file onto an empty track.
    return await import_documents(
        session,
        actor_id=actor_id,
        document=document,
        dry_run=dry_run,
        ip=ip,
        commit=commit,
        mode=mode,
        publish=publish,
    )


async def import_documents(
    session: AsyncSession,
    *,
    actor_id,
    document: str,
    dry_run: bool,
    ip: str | None,
    commit: bool = True,
    mode: str = "extend",
    publish: bool = False,
) -> dict:
    if mode not in {"extend", "replace"}:
        raise ContentError(400, "Import mode must be extend or replace")
    loaded = parse_document(document)
    catalog = _as_catalog(loaded)
    slug = "all" if catalog else _validate_track(loaded).slug

    async def apply() -> dict:
        changes = _blank_changes()
        files = {"modules": 0, "lessons": 0, "exercises": 0}
        tracks = catalog.tracks if catalog else [_validate_track(loaded)]
        if publish:
            _force_published(tracks)
        unpublished = _count_unpublished(tracks)
        target_id = "all"
        for parsed in tracks:
            part, track_id = await _import_one(session, parsed, actor_id=actor_id, mode=mode)
            _merge(changes, part)
            counts = _file_counts(parsed)
            for key, value in counts.items():
                files[key] += value
            target_id = str(track_id)
        summary = {
            "slug": slug,
            "mode": mode,
            "dry_run": dry_run,
            "publish": publish,
            "unpublished_lessons": unpublished,
            **files,
            **changes,
        }
        if len(tracks) != 1:
            target_id = "all"
        summary["target_id"] = target_id
        return summary

    if dry_run:
        nested = await session.begin_nested()
        try:
            summary = await apply()
        except Exception:
            await nested.rollback()
            raise
        await nested.rollback()
        summary.pop("target_id", None)
        return summary

    summary = await apply()
    target_id = summary.pop("target_id")
    # DECISION: import does not send a publish notification. Extend keeps the
    # lesson and exercise rows so learner progress stays attached. Replace
    # deletes that track's modules, and progress on them goes with them.
    await write_audit(
        session,
        actor_user_id=actor_id,
        action="content.import",
        target_type="track",
        target_id=target_id,
        details={key: value for key, value in summary.items() if key != "dry_run"},
        ip=ip,
    )
    if commit:
        await session.commit()
    return summary


def _force_published(tracks: list[ImportedTrack]) -> None:
    for track in tracks:
        for module in track.modules:
            module.status = "published"
            for lesson in module.lessons:
                lesson.status = "published"
                for exercise in lesson.exercises:
                    exercise.status = "published"


def _count_unpublished(tracks: list[ImportedTrack]) -> int:
    total = 0
    for track in tracks:
        for module in track.modules:
            if module.status != "published":
                total += len(module.lessons)
                continue
            for lesson in module.lessons:
                if lesson.status != "published":
                    total += 1
                    continue
                if any(exercise.status != "published" for exercise in lesson.exercises):
                    total += 1
    return total


def _as_catalog(loaded: dict) -> ImportedCatalog | None:
    if "tracks" in loaded and "slug" not in loaded:
        return _validate_catalog(loaded)
    return None


def _validate_catalog(document: dict) -> ImportedCatalog:
    try:
        catalog = ImportedCatalog.model_validate(document)
    except ValidationError as exc:
        raise ContentError(400, _validation_message(exc)) from exc
    slugs = [track.slug for track in catalog.tracks]
    if len(slugs) != len(set(slugs)):
        raise ContentError(400, "The file lists the same track more than once.")
    return catalog


def _file_counts(parsed: ImportedTrack) -> dict[str, int]:
    return {
        "modules": len(parsed.modules),
        "lessons": sum(len(module.lessons) for module in parsed.modules),
        "exercises": sum(
            len(lesson.exercises) for module in parsed.modules for lesson in module.lessons
        ),
    }


def _blank_changes() -> dict[str, int]:
    return {
        "added_modules": 0,
        "added_lessons": 0,
        "added_exercises": 0,
        "updated_modules": 0,
        "updated_lessons": 0,
        "updated_exercises": 0,
    }


def _merge(total: dict[str, int], part: dict[str, int]) -> None:
    for key in total:
        total[key] += part[key]


async def _import_one(
    session: AsyncSession,
    parsed: ImportedTrack,
    *,
    actor_id,
    mode: str,
) -> tuple[dict[str, int], uuid.UUID]:
    track = await session.scalar(select(Track).where(Track.slug == parsed.slug))
    if track is None:
        raise ContentError(404, f"Track {parsed.slug} not found")
    if mode == "replace":
        changes = await _replace_track(session, track, parsed, actor_id)
    else:
        changes = await _extend_track(session, parsed, actor_id)
    return changes, track.id


async def _replace_track(
    session: AsyncSession,
    track: Track,
    parsed: ImportedTrack,
    actor_id,
) -> dict[str, int]:
    _require_unique(parsed.modules, "modules")
    await session.execute(delete(Module).where(Module.track_id == track.id))
    _apply_track_text(track, parsed)
    added_lessons = 0
    added_exercises = 0
    for module_index, module in enumerate(parsed.modules, start=1):
        _require_unique(module.lessons, "lessons")
        module_row = Module(
            track_id=track.id,
            title=module.title.strip(),
            description=module.description.strip(),
            position=module_index,
            status=module.status,
        )
        session.add(module_row)
        await session.flush()
        for lesson_index, lesson in enumerate(module.lessons, start=1):
            lesson_row = _new_lesson(module_row.id, lesson, lesson_index, actor_id)
            session.add(lesson_row)
            await session.flush()
            added_lessons += 1
            added_exercises += await _replace_exercises(session, lesson_row, lesson)
    changes = _blank_changes()
    changes["added_modules"] = len(parsed.modules)
    changes["added_lessons"] = added_lessons
    changes["added_exercises"] = added_exercises
    return changes


async def _extend_track(
    session: AsyncSession,
    parsed: ImportedTrack,
    actor_id,
) -> dict[str, int]:
    track = await _track(session, parsed.slug)
    _require_unique(parsed.modules, "modules")
    _apply_track_text(track, parsed)
    changes = _blank_changes()
    modules = _by_title(list(track.modules), "modules")
    for module in parsed.modules:
        _require_unique(module.lessons, "lessons")
        title = module.title.strip()
        module_row = modules.get(title)
        lesson_rows: list[Lesson] = []
        if module_row is None:
            position = await _next_position(session, Module, Module.track_id, track.id)
            module_row = Module(
                track_id=track.id,
                title=title,
                description=module.description.strip(),
                position=position,
                status=module.status,
            )
            session.add(module_row)
            await session.flush()
            changes["added_modules"] += 1
            modules[title] = module_row
        else:
            lesson_rows = list(module_row.lessons)
            if _assign_module(module_row, module):
                changes["updated_modules"] += 1
        lessons = _by_title(lesson_rows, "lessons")
        for lesson in module.lessons:
            lesson_row = lessons.get(lesson.title.strip())
            if lesson_row is None:
                position = await _next_position(session, Lesson, Lesson.module_id, module_row.id)
                lesson_row = _new_lesson(module_row.id, lesson, position, actor_id)
                session.add(lesson_row)
                await session.flush()
                changes["added_lessons"] += 1
                existing_exercises: list[Exercise] = []
            else:
                existing_exercises = list(lesson_row.exercises)
                if _assign_lesson(lesson_row, lesson, actor_id):
                    changes["updated_lessons"] += 1
            added, updated = await _sync_exercises(session, lesson_row, lesson, existing_exercises)
            changes["added_exercises"] += added
            changes["updated_exercises"] += updated
    return changes


def _apply_track_text(track: Track, parsed: ImportedTrack) -> None:
    if parsed.name:
        track.name = parsed.name.strip()
    if parsed.description:
        track.description = parsed.description.strip()


def _require_unique(items, kind: str) -> None:
    seen: set[str] = set()
    for item in items:
        title = item.title.strip()
        if title in seen:
            raise ContentError(400, f"The file has two {kind} named {title}.")
        seen.add(title)


def _by_title(rows, kind: str) -> dict:
    found = {}
    for row in rows:
        title = row.title.strip()
        if title in found:
            raise ContentError(
                400,
                f"Two {kind} are both named {title}. Rename one before importing.",
            )
        found[title] = row
    return found


async def _next_position(session: AsyncSession, model, column, parent_id) -> int:
    current = await session.scalar(select(func.max(model.position)).where(column == parent_id))
    return (current or 0) + 1


def _new_lesson(module_id, lesson: ImportedLesson, position: int, actor_id) -> Lesson:
    return Lesson(
        module_id=module_id,
        title=lesson.title.strip(),
        summary=lesson.summary.strip(),
        body_markdown=lesson.body_markdown,
        position=position,
        status=lesson.status,
        is_demo=lesson.is_demo,
        source_type=lesson.source_type,
        source_attribution=lesson.source_attribution.strip(),
        source_url=lesson.cleaned_url(),
        license_note=lesson.license_note.strip(),
        created_by=actor_id,
        updated_by=actor_id,
    )


def _assign_module(row: Module, module: ImportedModule) -> bool:
    changed = False
    description = module.description.strip()
    if row.description != description:
        row.description = description
        changed = True
    if row.status != module.status:
        row.status = module.status
        changed = True
    return changed


def _assign_lesson(row: Lesson, lesson: ImportedLesson, actor_id) -> bool:
    fields = {
        "summary": lesson.summary.strip(),
        "body_markdown": lesson.body_markdown,
        "status": lesson.status,
        "is_demo": lesson.is_demo,
        "source_type": lesson.source_type,
        "source_attribution": lesson.source_attribution.strip(),
        "source_url": lesson.cleaned_url(),
        "license_note": lesson.license_note.strip(),
    }
    changed = False
    for key, value in fields.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        row.updated_by = actor_id
    return changed


def _exercise_payload(exercise: ImportedExercise) -> dict:
    return exercise.model_dump(exclude={"status", "order"})


async def _replace_exercises(
    session: AsyncSession, lesson_row: Lesson, lesson: ImportedLesson
) -> int:
    _require_unique_orders(lesson.exercises, lesson.title)
    for exercise_index, exercise in enumerate(lesson.exercises, start=1):
        session.add(
            Exercise(
                lesson_id=lesson_row.id,
                position=exercise_index,
                type=exercise.type,
                status=exercise.status,
                data=_exercise_payload(exercise),
            )
        )
    await session.flush()
    return len(lesson.exercises)


async def _sync_exercises(
    session: AsyncSession,
    lesson_row: Lesson,
    lesson: ImportedLesson,
    existing_rows: list[Exercise],
) -> tuple[int, int]:
    _require_unique_orders(lesson.exercises, lesson.title)
    positions = [row.position for row in existing_rows]
    if len(positions) != len(set(positions)):
        raise ContentError(
            400,
            f"{lesson.title} has two exercises with the same order. Reorder them before importing.",
        )
    existing = {row.position: row for row in existing_rows}
    taken = set(existing)
    added = 0
    updated = 0
    for exercise_index, exercise in enumerate(lesson.exercises, start=1):
        payload = _exercise_payload(exercise)
        # DECISION: missing order means "nth exercise in this lesson file", so a
        # downloaded file can be uploaded again without appending duplicates.
        position = exercise.order if exercise.order is not None else exercise_index
        row = existing.get(position)
        if row is None:
            session.add(
                Exercise(
                    lesson_id=lesson_row.id,
                    position=position,
                    type=exercise.type,
                    status=exercise.status,
                    data=payload,
                )
            )
            taken.add(position)
            added += 1
            continue
        taken.add(position)
        if row.type != exercise.type or row.status != exercise.status or row.data != payload:
            row.type = exercise.type
            row.status = exercise.status
            row.data = payload
            updated += 1
    await session.flush()
    return added, updated


def _require_unique_orders(exercises: list[ImportedExercise], title: str) -> None:
    seen: set[int] = set()
    for exercise in exercises:
        if exercise.order is None:
            continue
        if exercise.order in seen:
            raise ContentError(400, f"{title} has two exercises with order {exercise.order}.")
        seen.add(exercise.order)


def _validate_track(document: dict) -> ImportedTrack:
    try:
        return ImportedTrack.model_validate(document)
    except ValidationError as exc:
        raise ContentError(400, _validation_message(exc)) from exc


def _validation_message(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"])
    message = error["msg"]
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return f"{location}: {message}" if location else message


async def _track(session: AsyncSession, slug: str) -> Track:
    track = await session.scalar(
        select(Track)
        .where(Track.slug == slug)
        .options(
            selectinload(Track.modules).selectinload(Module.lessons).selectinload(Lesson.exercises)
        )
    )
    if track is None:
        raise ContentError(404, "Track not found")
    return track


def _lesson_document(lesson: Lesson) -> dict:
    return {
        "title": lesson.title,
        "summary": lesson.summary,
        "body_markdown": lesson.body_markdown,
        "status": lesson.status,
        "is_demo": lesson.is_demo,
        "source_type": lesson.source_type,
        "source_attribution": lesson.source_attribution,
        "source_url": lesson.source_url,
        "license_note": lesson.license_note,
        "exercises": [
            {
                **exercise.data,
                "status": exercise.status,
                "order": exercise.position,
            }
            for exercise in lesson.exercises
        ],
    }


def _track_document(track: Track) -> dict:
    return {
        "slug": track.slug,
        "name": track.name,
        "description": track.description,
        "modules": [
            {
                "title": module.title,
                "description": module.description,
                "status": module.status,
                "lessons": [_lesson_document(lesson) for lesson in module.lessons],
            }
            for module in track.modules
        ],
    }
