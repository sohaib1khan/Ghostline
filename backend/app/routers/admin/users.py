"""Create, read, update, and delete accounts — super admin only."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.users import (
    AdminCreateIn,
    AdminUserOut,
    PasswordResetIn,
    Status,
    TrackSlugsIn,
    UserPatchIn,
)
from app.security.deps import require_super_admin
from app.security.requests import client_ip
from app.services.users import (
    UserAdminError,
    approve_user,
    create_user,
    delete_user,
    list_users,
    reject_user,
    reset_password,
    revoke_sessions,
    set_tracks,
    update_user,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _raise(exc: UserAdminError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("", response_model=list[AdminUserOut])
async def users(
    status: Status | None = Query(default=None),
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_users(db, status)


@router.post("", response_model=AdminUserOut, status_code=201)
async def add_user(
    payload: AdminCreateIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_user(
            db,
            actor=actor,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            track_slugs=payload.track_slugs,
            ip=client_ip(request),
        )
    except UserAdminError as exc:
        _raise(exc)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: UUID,
    payload: UserPatchIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await update_user(
            db,
            actor=actor,
            user_id=user_id,
            role=payload.role,
            status=payload.status,
            ip=client_ip(request),
        )
    except UserAdminError as exc:
        _raise(exc)


@router.delete("/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await delete_user(db, actor=actor, user_id=user_id, ip=client_ip(request))
    except UserAdminError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/{user_id}/approve", response_model=AdminUserOut)
async def approve(
    user_id: UUID,
    payload: TrackSlugsIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await approve_user(
            db,
            actor=actor,
            user_id=user_id,
            track_slugs=payload.track_slugs,
            ip=client_ip(request),
        )
    except UserAdminError as exc:
        _raise(exc)


@router.post("/{user_id}/reject", response_model=AdminUserOut)
async def reject(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await reject_user(db, actor=actor, user_id=user_id, ip=client_ip(request))
    except UserAdminError as exc:
        _raise(exc)


@router.put("/{user_id}/tracks", response_model=AdminUserOut)
async def tracks(
    user_id: UUID,
    payload: TrackSlugsIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await set_tracks(
            db,
            actor=actor,
            user_id=user_id,
            track_slugs=payload.track_slugs,
            ip=client_ip(request),
        )
    except UserAdminError as exc:
        _raise(exc)


@router.post("/{user_id}/reset-password", status_code=204)
async def reset(
    user_id: UUID,
    payload: PasswordResetIn,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await reset_password(
            db,
            actor=actor,
            user_id=user_id,
            password=payload.password,
            ip=client_ip(request),
        )
    except UserAdminError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.post("/{user_id}/revoke-sessions", status_code=204)
async def revoke(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await revoke_sessions(db, actor=actor, user_id=user_id, ip=client_ip(request))
    except UserAdminError as exc:
        _raise(exc)
    return Response(status_code=204)
