"""Learner mistake journal endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import current_user
from app.services.journal import delete_journal, usual_slips

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/slips")
async def slips(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await usual_slips(db, user)


@router.delete("")
async def clear_journal(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await delete_journal(db, user)
