"""Learner certificates for completed tracks."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import current_user
from app.services.certificates import certificate_for_track, list_certificates
from app.services.content_store import ContentError

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("")
async def certificates(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_certificates(db, user)


@router.get("/{slug}")
async def certificate(
    slug: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await certificate_for_track(db, user, slug)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
