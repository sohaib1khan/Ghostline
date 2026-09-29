"""Admin AI settings, connection test, and lesson drafts."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models.user import User
from app.schemas.ai import DraftLessonIn
from app.security.deps import require_admin
from app.security.rate_limit import limiter
from app.security.requests import client_ip
from app.services.ai.config import AiConfigIn, load_config, save_config
from app.services.ai.drafter import draft_lesson, test_connection
from app.services.ai.errors import AiError
from app.services.audit import write_audit

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


def _raise(exc: AiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/settings")
@limiter.limit(lambda: f"{get_settings().rate_limit_ai}/minute")
async def read_ai_settings(
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    del request
    return (await load_config(db)).public()


@router.put("/settings")
@limiter.limit(lambda: f"{get_settings().rate_limit_ai}/minute")
async def update_ai_settings(
    body: AiConfigIn,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        saved = await save_config(db, body)
    except AiError as exc:
        _raise(exc)
    await write_audit(
        db,
        actor_user_id=actor.id,
        action="ai.settings_update",
        target_type="ai",
        details={
            "provider": saved.provider,
            "model": saved.model,
            "enabled": saved.enabled,
            "api_key_set": bool(saved.api_key),
            "api_key_replaced": bool(body.api_key),
            "api_key_cleared": body.clear_api_key,
        },
        ip=client_ip(request),
    )
    await db.commit()
    return saved.public()


@router.post("/test")
@limiter.limit(lambda: f"{get_settings().rate_limit_ai}/minute")
async def test_ai(
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await test_connection(db, actor=actor, ip=client_ip(request))
    except AiError as exc:
        _raise(exc)


@router.post("/draft-lesson", status_code=201)
@limiter.limit(lambda: f"{get_settings().rate_limit_ai}/minute")
async def generate_draft(
    body: DraftLessonIn,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await draft_lesson(db, actor=actor, payload=body, ip=client_ip(request))
    except AiError as exc:
        _raise(exc)
