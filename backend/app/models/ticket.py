"""Bug report tickets and reply threads."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

CATEGORIES = (
    "page_broken",
    "check_failed",
    "editor_typing",
    "ghostwalk_games",
    "wrong_content",
    "account_access",
    "other",
)

STATUSES = ("open", "waiting_on_user", "resolved", "closed")


class Ticket(IdMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category in ("
            "'page_broken','check_failed','editor_typing','ghostwalk_games',"
            "'wrong_content','account_access','other'"
            ")",
            name="ck_tickets_category",
        ),
        CheckConstraint(
            "status in ('open','waiting_on_user','resolved','closed')",
            name="ck_tickets_status",
        ),
    )

    public_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    page_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    page_path: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    viewport: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    unread_for_creator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unread_for_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )


class TicketMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "ticket_messages"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_from_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
