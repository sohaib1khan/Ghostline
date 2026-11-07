"""Learner bug reports and support replies."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.tickets import (
    TicketCreateIn,
    TicketDetailOut,
    TicketReplyIn,
    TicketStatusIn,
    TicketSummaryOut,
    TicketUnreadOut,
)
from app.security.deps import current_user, require_super_admin
from app.security.rate_limit import limiter
from app.services.tickets import (
    TicketError,
    create_ticket,
    get_ticket,
    list_my_tickets,
    list_staff_tickets,
    reply_ticket,
    set_status,
    unread_count,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])
admin_router = APIRouter(prefix="/admin/tickets", tags=["admin-tickets"])


def _http(exc: TicketError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/unread", response_model=TicketUnreadOut)
@limiter.limit("60/minute")
async def get_unread(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketUnreadOut:
    return TicketUnreadOut(count=await unread_count(db, user))


@router.get("", response_model=list[TicketSummaryOut])
@limiter.limit("60/minute")
async def my_tickets(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TicketSummaryOut]:
    rows = await list_my_tickets(db, user)
    return [TicketSummaryOut.model_validate(row) for row in rows]


@router.post("", response_model=TicketDetailOut, status_code=201)
@limiter.limit("10/minute")
async def open_ticket(
    request: Request,
    payload: TicketCreateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    try:
        row = await create_ticket(db, user, payload)
    except TicketError as exc:
        raise _http(exc) from exc
    return TicketDetailOut.model_validate(row)


@router.get("/{ticket_id}", response_model=TicketDetailOut)
@limiter.limit("60/minute")
async def read_ticket(
    request: Request,
    ticket_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    try:
        row = await get_ticket(db, user, ticket_id)
    except TicketError as exc:
        raise _http(exc) from exc
    return TicketDetailOut.model_validate(row)


@router.post("/{ticket_id}/reply", response_model=TicketDetailOut)
@limiter.limit("30/minute")
async def post_reply(
    request: Request,
    ticket_id: UUID,
    payload: TicketReplyIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    try:
        row = await reply_ticket(db, user, ticket_id, body=payload.body)
    except TicketError as exc:
        raise _http(exc) from exc
    return TicketDetailOut.model_validate(row)


@admin_router.get("", response_model=list[TicketSummaryOut])
@limiter.limit("60/minute")
async def staff_tickets(
    request: Request,
    status: str | None = Query(default=None),
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TicketSummaryOut]:
    del user
    rows = await list_staff_tickets(db, status=status)
    return [TicketSummaryOut.model_validate(row) for row in rows]


@admin_router.patch("/{ticket_id}/status", response_model=TicketDetailOut)
@limiter.limit("30/minute")
async def patch_status(
    request: Request,
    ticket_id: UUID,
    payload: TicketStatusIn,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    try:
        row = await set_status(db, user, ticket_id, status=payload.status)
    except TicketError as exc:
        raise _http(exc) from exc
    return TicketDetailOut.model_validate(row)
