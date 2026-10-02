"""Admin content management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.content import (
    ExerciseIn,
    ExercisePatch,
    ImportIn,
    LessonIn,
    LessonPatch,
    ModuleIn,
    ModulePatch,
    ParseExerciseIn,
    ReorderIn,
    TestCheckIn,
    TrackPatch,
)
from app.security.deps import require_super_admin
from app.security.requests import client_ip
from app.services.content_io import (
    export_catalog,
    export_lesson,
    export_track,
    import_documents,
    parse_exercise_text,
)
from app.services.content_store import (
    ContentError,
    content_tree,
    create_exercise,
    create_lesson,
    create_module,
    delete_exercise,
    delete_lesson,
    delete_module,
    get_lesson,
    publish_lesson,
    publish_track,
    reorder,
    run_test_check,
    update_exercise,
    update_lesson,
    update_module,
    update_track,
)
from app.services.content_store import (
    preview_lesson as lesson_preview,
)

router = APIRouter(prefix="/admin", tags=["admin-content"])


def _raise(exc: ContentError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/content/tree")
async def tree(_: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> dict:
    return {"tracks": await content_tree(db)}


@router.patch("/tracks/{track_id}")
async def patch_track(
    track_id: UUID,
    payload: TrackPatch,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_track(
            db, actor=actor, track_id=track_id, patch=payload, ip=client_ip(request)
        )
    except ContentError as exc:
        _raise(exc)


@router.post("/modules", status_code=201)
async def add_module(
    payload: ModuleIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_module(db, actor=actor, payload=payload, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)


@router.patch("/modules/{module_id}")
async def patch_module(
    module_id: UUID,
    payload: ModulePatch,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_module(
            db, actor=actor, module_id=module_id, patch=payload, ip=client_ip(request)
        )
    except ContentError as exc:
        _raise(exc)


@router.delete("/modules/{module_id}", status_code=204)
async def remove_module(
    module_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await delete_module(db, actor=actor, module_id=module_id, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/lessons", status_code=201)
async def add_lesson(
    payload: LessonIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_lesson(db, actor=actor, payload=payload, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)


@router.get("/lessons/{lesson_id}")
async def read_lesson(
    lesson_id: UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_lesson(db, lesson_id)
    except ContentError as exc:
        _raise(exc)


@router.get("/lessons/{lesson_id}/preview")
async def preview_lesson(
    lesson_id: UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await lesson_preview(db, lesson_id)
    except ContentError as exc:
        _raise(exc)


@router.patch("/lessons/{lesson_id}")
async def patch_lesson(
    lesson_id: UUID,
    payload: LessonPatch,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_lesson(
            db, actor=actor, lesson_id=lesson_id, patch=payload, ip=client_ip(request)
        )
    except ContentError as exc:
        _raise(exc)


@router.delete("/lessons/{lesson_id}", status_code=204)
async def remove_lesson(
    lesson_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await delete_lesson(db, actor=actor, lesson_id=lesson_id, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/lessons/{lesson_id}/publish")
async def publish(
    lesson_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await publish_lesson(db, actor=actor, lesson_id=lesson_id, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)


@router.post("/tracks/{track_id}/publish")
async def publish_track_content(
    track_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await publish_track(db, actor=actor, track_id=track_id, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)


@router.post("/exercises", status_code=201)
async def add_exercise(
    payload: ExerciseIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_exercise(db, actor=actor, payload=payload, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)


@router.patch("/exercises/{exercise_id}")
async def patch_exercise(
    exercise_id: UUID,
    payload: ExercisePatch,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_exercise(
            db, actor=actor, exercise_id=exercise_id, patch=payload, ip=client_ip(request)
        )
    except ContentError as exc:
        _raise(exc)


@router.delete("/exercises/{exercise_id}", status_code=204)
async def remove_exercise(
    exercise_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await delete_exercise(db, actor=actor, exercise_id=exercise_id, ip=client_ip(request))
    except ContentError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/reorder", status_code=204)
async def reorder_items(
    payload: ReorderIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await reorder(
            db,
            actor=actor,
            kind=payload.kind,
            parent_id=payload.parent_id,
            ids=payload.ids,
            ip=client_ip(request),
        )
    except ContentError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/exercises/test-check")
async def test_check(
    payload: TestCheckIn,
    _: User = Depends(require_super_admin),
) -> dict:
    return run_test_check(payload.data, payload.attempt, payload.output)


@router.post("/content/parse-exercise")
async def parse_exercise(
    payload: ParseExerciseIn,
    _: User = Depends(require_super_admin),
) -> dict:
    try:
        return {"data": parse_exercise_text(payload.text, payload.format)}
    except ContentError as exc:
        _raise(exc)


@router.get("/export")
async def export_content(
    track: str | None = Query(default=None, min_length=1, max_length=40),
    lesson: UUID | None = None,
    fmt: str = Query(default="yaml", alias="format", pattern="^(yaml|json)$"),
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if lesson is not None and track is not None:
        raise HTTPException(status_code=400, detail="Export a track or a lesson, not both")
    extension = "json" if fmt == "json" else "yaml"
    try:
        if lesson is not None:
            body, media, filename = await export_lesson(db, lesson, fmt)
        elif track == "all":
            body, media = await export_catalog(db, fmt)
            filename = f"ghostline.{extension}"
        elif track:
            body, media = await export_track(db, track, fmt)
            filename = f"{track}.{extension}"
        else:
            raise HTTPException(status_code=400, detail="Choose a track, all tracks, or a lesson")
    except ContentError as exc:
        _raise(exc)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_content(
    payload: ImportIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await import_documents(
            db,
            actor_id=actor.id,
            document=payload.document,
            dry_run=payload.dry_run,
            ip=client_ip(request),
            mode=payload.mode,
            publish=payload.publish,
        )
    except ContentError as exc:
        _raise(exc)
