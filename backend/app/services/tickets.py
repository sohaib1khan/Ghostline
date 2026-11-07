"""Bug report tickets — create, list, reply, unread counts."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import CATEGORIES, STATUSES, Ticket, TicketMessage
from app.models.user import User
from app.schemas.tickets import TicketCreateIn
from app.security.roles import is_super_admin

CATEGORY_LABELS = {
    "page_broken": "Page won't load or looks broken",
    "check_failed": "Check / submit failed",
    "editor_typing": "Editor or typing issue",
    "ghostwalk_games": "Ghostwalk or games broken",
    "wrong_content": "Wrong content or answer",
    "account_access": "Account or login problem",
    "other": "Something else",
}


class TicketError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _display_name(user: User | None) -> str:
    if user is None:
        return "Unknown"
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


async def _unique_public_id(session: AsyncSession) -> str:
    for _ in range(12):
        code = f"BUG-{secrets.token_hex(3).upper()}"
        exists = await session.scalar(select(Ticket.id).where(Ticket.public_id == code))
        if exists is None:
            return code
    raise TicketError(500, "Could not assign a bug id")


def _subject_from(payload: TicketCreateIn) -> str:
    text = (payload.subject or "").strip()
    if text:
        return text[:160]
    label = CATEGORY_LABELS.get(payload.category, "Bug report")
    path = (payload.page_path or "").strip() or "/"
    return f"{label} · {path}"[:160]


def _safe_context(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False)[:4000]
    except json.JSONDecodeError:
        return text[:4000]


def serialize_message(message: TicketMessage, author: User | None) -> dict:
    return {
        "id": message.id,
        "body": message.body,
        "is_from_staff": message.is_from_staff,
        "author_name": _display_name(author),
        "created_at": message.created_at,
    }


def serialize_summary(ticket: Ticket, *, unread: bool, creator: User | None = None) -> dict:
    return {
        "id": ticket.id,
        "public_id": ticket.public_id,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        "page_path": ticket.page_path,
        "created_at": ticket.created_at,
        "last_message_at": ticket.last_message_at,
        "unread": unread,
        "creator_name": _display_name(creator) if creator else None,
        "creator_email": creator.email if creator else None,
    }


def serialize_detail(
    ticket: Ticket,
    *,
    unread: bool,
    creator: User | None,
    authors: dict[uuid.UUID, User],
) -> dict:
    body = serialize_summary(ticket, unread=unread, creator=creator)
    body.update(
        {
            "page_url": ticket.page_url,
            "user_agent": ticket.user_agent,
            "viewport": ticket.viewport,
            "context_json": ticket.context_json,
            "messages": [
                serialize_message(message, authors.get(message.author_user_id))
                for message in ticket.messages
            ],
        }
    )
    return body


async def create_ticket(session: AsyncSession, user: User, payload: TicketCreateIn) -> dict:
    if payload.category not in CATEGORIES:
        raise TicketError(400, "Unknown category")
    now = datetime.now(UTC)
    ticket = Ticket(
        public_id=await _unique_public_id(session),
        created_by_user_id=user.id,
        subject=_subject_from(payload),
        category=payload.category,
        status="open",
        page_url=(payload.page_url or "")[:500],
        page_path=(payload.page_path or "")[:300],
        user_agent=(payload.user_agent or "")[:400],
        viewport=(payload.viewport or "")[:40],
        context_json=_safe_context(payload.context_json),
        last_message_at=now,
        unread_for_creator=False,
        unread_for_staff=True,
    )
    session.add(ticket)
    await session.flush()
    session.add(
        TicketMessage(
            ticket_id=ticket.id,
            author_user_id=user.id,
            body=payload.body.strip(),
            is_from_staff=False,
        )
    )
    await session.commit()
    return await get_ticket(session, user, ticket.id)


async def list_my_tickets(session: AsyncSession, user: User) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(Ticket)
                .where(Ticket.created_by_user_id == user.id)
                .order_by(Ticket.last_message_at.desc())
                .limit(100)
            )
        ).all()
    )
    return [
        serialize_summary(ticket, unread=bool(ticket.unread_for_creator), creator=user)
        for ticket in rows
    ]


async def list_staff_tickets(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    stmt = select(Ticket).order_by(Ticket.unread_for_staff.desc(), Ticket.last_message_at.desc())
    if status and status in STATUSES:
        stmt = stmt.where(Ticket.status == status)
    rows = list((await session.scalars(stmt.limit(limit))).all())
    creators = await _users_by_id(session, {ticket.created_by_user_id for ticket in rows})
    return [
        serialize_summary(
            ticket,
            unread=bool(ticket.unread_for_staff),
            creator=creators.get(ticket.created_by_user_id),
        )
        for ticket in rows
    ]


async def _users_by_id(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = list((await session.scalars(select(User).where(User.id.in_(ids)))).all())
    return {row.id: row for row in rows}


async def _load_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket:
    ticket = await session.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.messages))
    )
    if ticket is None:
        raise TicketError(404, "Ticket not found")
    return ticket


async def get_ticket(session: AsyncSession, user: User, ticket_id: uuid.UUID) -> dict:
    ticket = await _load_ticket(session, ticket_id)
    staff = is_super_admin(user.role)
    if not staff and ticket.created_by_user_id != user.id:
        raise TicketError(404, "Ticket not found")
    if staff:
        if ticket.unread_for_staff:
            ticket.unread_for_staff = False
            await session.commit()
        unread = False
    else:
        if ticket.unread_for_creator:
            ticket.unread_for_creator = False
            await session.commit()
        unread = False
    authors = await _users_by_id(
        session,
        {ticket.created_by_user_id, *(message.author_user_id for message in ticket.messages)},
    )
    return serialize_detail(
        ticket,
        unread=unread,
        creator=authors.get(ticket.created_by_user_id),
        authors=authors,
    )


async def reply_ticket(
    session: AsyncSession,
    user: User,
    ticket_id: uuid.UUID,
    *,
    body: str,
) -> dict:
    ticket = await _load_ticket(session, ticket_id)
    staff = is_super_admin(user.role)
    if not staff and ticket.created_by_user_id != user.id:
        raise TicketError(404, "Ticket not found")
    if ticket.status == "closed" and not staff:
        raise TicketError(400, "This ticket is closed")
    text = body.strip()
    if not text:
        raise TicketError(400, "Write a message")
    now = datetime.now(UTC)
    session.add(
        TicketMessage(
            ticket_id=ticket.id,
            author_user_id=user.id,
            body=text,
            is_from_staff=staff,
        )
    )
    ticket.last_message_at = now
    if staff:
        ticket.unread_for_creator = True
        ticket.unread_for_staff = False
        if ticket.status in {"open", "waiting_on_user"}:
            ticket.status = "waiting_on_user"
    else:
        ticket.unread_for_staff = True
        ticket.unread_for_creator = False
        if ticket.status == "waiting_on_user":
            ticket.status = "open"
    await session.commit()
    return await get_ticket(session, user, ticket.id)


async def set_status(
    session: AsyncSession,
    user: User,
    ticket_id: uuid.UUID,
    *,
    status: str,
) -> dict:
    if not is_super_admin(user.role):
        raise TicketError(403, "Only the support desk can change status")
    if status not in STATUSES:
        raise TicketError(400, "Unknown status")
    ticket = await _load_ticket(session, ticket_id)
    ticket.status = status
    if status in {"resolved", "closed"}:
        ticket.unread_for_staff = False
    await session.commit()
    return await get_ticket(session, user, ticket.id)


async def unread_count(session: AsyncSession, user: User) -> int:
    if is_super_admin(user.role):
        value = await session.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.unread_for_staff.is_(True))
        )
        return int(value or 0)
    value = await session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(
            Ticket.created_by_user_id == user.id,
            Ticket.unread_for_creator.is_(True),
        )
    )
    return int(value or 0)
