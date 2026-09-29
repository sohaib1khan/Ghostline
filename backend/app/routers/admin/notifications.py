"""Admin notification channels."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.notifications import ChannelIn, ChannelListOut, ChannelOut, TestOut
from app.security.deps import require_admin
from app.security.requests import client_ip
from app.services.notifications.channels import (
    ChannelError,
    create_channel,
    delete_channel,
    list_channels,
    send_test,
    update_channel,
)

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


def _raise(exc: ChannelError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/channels", response_model=ChannelListOut)
async def channels(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_channels(db)


@router.post("/channels", response_model=ChannelOut, status_code=201)
async def add_channel(
    payload: ChannelIn,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_channel(
            db,
            actor_id=actor.id,
            name=payload.name,
            provider=payload.provider,
            events=list(payload.events),
            is_enabled=payload.is_enabled,
            config=payload.config,
            ip=client_ip(request),
        )
    except ChannelError as exc:
        _raise(exc)


@router.put("/channels/{channel_id}", response_model=ChannelOut)
async def edit_channel(
    channel_id: UUID,
    payload: ChannelIn,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_channel(
            db,
            actor_id=actor.id,
            channel_id=channel_id,
            name=payload.name,
            provider=payload.provider,
            events=list(payload.events),
            is_enabled=payload.is_enabled,
            config=payload.config,
            ip=client_ip(request),
        )
    except ChannelError as exc:
        _raise(exc)


@router.delete("/channels/{channel_id}", status_code=204)
async def remove_channel(
    channel_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await delete_channel(db, actor_id=actor.id, channel_id=channel_id, ip=client_ip(request))
    except ChannelError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/channels/{channel_id}/test", response_model=TestOut)
async def test_channel(
    channel_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await send_test(db, actor_id=actor.id, channel_id=channel_id, ip=client_ip(request))
    except ChannelError as exc:
        _raise(exc)
