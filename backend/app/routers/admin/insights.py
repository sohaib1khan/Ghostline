"""Staff Leaderboard and usage insights."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import require_admin
from app.services.insights import staff_insights

router = APIRouter(prefix="/admin/insights", tags=["admin-insights"])


@router.get("")
async def insights(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await staff_insights(db)
