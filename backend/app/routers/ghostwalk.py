"""Ghostwalk learner and admin API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import current_user, require_super_admin
from app.services.content_store import ContentError
from app.services.ghostwalk import (
    admin_list_levels,
    admin_reorder,
    admin_test_solution,
    admin_upsert_level,
    get_level_for_user,
    list_levels_for_user,
    submit_level,
    world_source,
)

router = APIRouter(prefix="/ghostwalk", tags=["ghostwalk"])
admin_router = APIRouter(prefix="/admin/ghostwalk", tags=["admin-ghostwalk"])


class SubmitIn(BaseModel):
    code: str = Field(default="", max_length=12_000)
    actions: list = Field(default_factory=list, max_length=2_000)
    hints_used: int = Field(default=0, ge=0, le=50)


class LevelIn(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    order: int = Field(default=0, ge=0, le=10_000)
    title: str = Field(min_length=1, max_length=120)
    concept: str = Field(default="", max_length=120)
    intro_markdown: str = Field(default="", max_length=20_000)
    grid: list
    start: dict
    allowed: list = Field(default_factory=list)
    goal: dict = Field(default_factory=dict)
    max_steps: int = Field(default=500, ge=1, le=10_000)
    mode: str = Field(default="free")
    language: str = Field(default="python", max_length=32)
    starter_code: str = Field(default="", max_length=12_000)
    solution: str = Field(default="", max_length=12_000)
    hints: list[str] = Field(default_factory=list)
    par_lines: int = Field(default=1, ge=1, le=500)
    xp: int = Field(default=20, ge=0, le=500)
    status: str = Field(default="draft")
    python_lesson_slug: str | None = None


class ReorderIn(BaseModel):
    ordered_ids: list[UUID] = Field(default_factory=list, max_length=200)


def _raise(exc: ContentError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/world.py", response_class=PlainTextResponse)
async def get_world_py() -> str:
    return world_source()


@router.get("/levels")
async def levels(
    language: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_levels_for_user(db, user, language=language)


@router.get("/levels/{slug}")
async def level(
    slug: str,
    memory: bool = Query(default=False),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_level_for_user(db, user, slug, memory_mode=memory)
    except ContentError as exc:
        _raise(exc)


@router.post("/levels/{slug}/submit")
async def submit(
    slug: str,
    payload: SubmitIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await submit_level(
            db,
            user,
            slug,
            code=payload.code,
            actions=payload.actions,
            hints_used=payload.hints_used,
        )
    except ContentError as exc:
        _raise(exc)


@admin_router.get("/levels")
async def admin_levels(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {"levels": await admin_list_levels(db)}


@admin_router.post("/levels", status_code=201)
async def admin_create_level(
    payload: LevelIn,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await admin_upsert_level(db, payload.model_dump())
    except ContentError as exc:
        _raise(exc)


@admin_router.put("/levels/{level_id}")
async def admin_update_level(
    level_id: UUID,
    payload: LevelIn,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await admin_upsert_level(db, payload.model_dump(), level_id=level_id)
    except ContentError as exc:
        _raise(exc)


@admin_router.post("/levels/reorder")
async def admin_reorder_levels(
    payload: ReorderIn,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {"levels": await admin_reorder(db, payload.ordered_ids)}


@admin_router.post("/levels/{level_id}/test-solution")
async def admin_test(
    level_id: UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await admin_test_solution(db, level_id)
    except ContentError as exc:
        _raise(exc)


@admin_router.get("/export")
async def admin_export(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    import yaml

    levels = await admin_list_levels(db)
    body = yaml.safe_dump(
        {
            "levels": [
                {
                    "slug": item["slug"],
                    "order": item["order"],
                    "title": item["title"],
                    "concept": item["concept"],
                    "intro_markdown": item["intro_markdown"],
                    "grid": item["grid"],
                    "start": item["start"],
                    "allowed": item["allowed"],
                    "goal": item["goal"],
                    "max_steps": item["max_steps"],
                    "mode": item["mode"],
                    "starter_code": item["starter_code"],
                    "solution": item["solution"],
                    "hints": item["hints"],
                    "par_lines": item["par_lines"],
                    "xp": item["xp"],
                    "status": item["status"],
                    "python_lesson_slug": item.get("python_lesson_slug"),
                }
                for item in levels
            ]
        },
        sort_keys=False,
        allow_unicode=True,
    )
    return Response(content=body, media_type="application/x-yaml")


class ImportIn(BaseModel):
    """YAML/JSON text in `document`, or a parsed `levels` list / single level fields."""

    document: str | None = Field(default=None, max_length=500_000)
    levels: list | None = None
    dry_run: bool = True
    publish: bool = False


@admin_router.post("/import")
async def admin_import(
    payload: ImportIn,
    dry_run: bool | None = Query(default=None),
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.ghostwalk import admin_import_levels

    check_only = payload.dry_run if dry_run is None else dry_run
    if payload.document and payload.document.strip():
        source: str | dict = payload.document
    elif payload.levels is not None:
        source = {"levels": payload.levels}
    else:
        # Allow posting a bare level object fields via extra keys — prefer document.
        raise HTTPException(
            status_code=400,
            detail="Send {document: '<yaml>'} or {levels: [...]}",
        )
    try:
        return await admin_import_levels(
            db,
            document=source,
            dry_run=check_only,
            publish=payload.publish,
        )
    except ContentError as exc:
        _raise(exc)
