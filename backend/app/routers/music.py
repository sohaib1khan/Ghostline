"""Ambient music playlist for learners; super admin can edit tracks."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import current_user, require_super_admin
from app.security.rate_limit import limiter
from app.security.requests import client_ip
from app.services.audit import write_audit
from app.services.music import get_playlist, save_playlist

router = APIRouter(tags=["music"])


class TrackIn(BaseModel):
    title: str = Field(default="", max_length=80)
    url: str = Field(default="", max_length=500)


class PlaylistIn(BaseModel):
    enabled: bool = True
    rotate: bool = True
    tracks: list[TrackIn] = Field(default_factory=list, max_length=5)


@router.get("/music/playlist")
@limiter.limit("60/minute")
async def read_playlist(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    del request, user
    return await get_playlist(db)


@router.put("/admin/music/playlist")
@limiter.limit("20/minute")
async def write_playlist(
    request: Request,
    body: PlaylistIn,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    saved = await save_playlist(
        db,
        {
            "enabled": body.enabled,
            "rotate": body.rotate,
            "tracks": [track.model_dump() for track in body.tracks],
        },
    )
    await write_audit(
        db,
        actor_user_id=user.id,
        action="music.playlist",
        target_type="settings",
        target_id="ambient_music_playlist",
        details={"enabled": saved["enabled"], "tracks": len(saved["tracks"])},
        ip=client_ip(request),
    )
    await db.commit()
    return saved
