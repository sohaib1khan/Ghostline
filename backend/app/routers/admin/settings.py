"""App settings an admin can change. Secrets stay out of this page."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import require_admin
from app.security.requests import client_ip
from app.services.audit import write_audit
from app.services.games import LEADERBOARD_KEY
from app.services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


class SettingsIn(BaseModel):
    leaderboard_enabled: bool


def _enabled(stored) -> bool:
    return isinstance(stored, dict) and bool(stored.get("enabled"))


@router.get("")
async def read_settings(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    del user
    return {"leaderboard_enabled": _enabled(await get_setting(db, LEADERBOARD_KEY))}


@router.put("")
async def update_settings(
    body: SettingsIn,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await set_setting(db, LEADERBOARD_KEY, {"enabled": body.leaderboard_enabled})
    await write_audit(
        db,
        actor_user_id=user.id,
        action="settings.update",
        target_type="settings",
        target_id=LEADERBOARD_KEY,
        details={"leaderboard_enabled": body.leaderboard_enabled},
        ip=client_ip(request),
    )
    await db.commit()
    return {"leaderboard_enabled": body.leaderboard_enabled}
