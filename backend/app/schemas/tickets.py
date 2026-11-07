"""Bug report ticket payloads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TicketCategory = Literal[
    "page_broken",
    "check_failed",
    "editor_typing",
    "ghostwalk_games",
    "wrong_content",
    "account_access",
    "other",
]
TicketStatus = Literal["open", "waiting_on_user", "resolved", "closed"]


class TicketCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: TicketCategory = "other"
    subject: str = Field(default="", max_length=160)
    body: str = Field(min_length=1, max_length=4000)
    page_url: str = Field(default="", max_length=500)
    page_path: str = Field(default="", max_length=300)
    user_agent: str = Field(default="", max_length=400)
    viewport: str = Field(default="", max_length=40)
    context_json: str = Field(default="", max_length=4000)


class TicketReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)


class TicketStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TicketStatus


class TicketMessageOut(BaseModel):
    id: UUID
    body: str
    is_from_staff: bool
    author_name: str
    created_at: datetime


class TicketSummaryOut(BaseModel):
    id: UUID
    public_id: str
    subject: str
    category: str
    status: str
    page_path: str
    created_at: datetime
    last_message_at: datetime
    unread: bool
    creator_name: str | None = None
    creator_email: str | None = None


class TicketDetailOut(TicketSummaryOut):
    page_url: str
    user_agent: str
    viewport: str
    context_json: str
    messages: list[TicketMessageOut]


class TicketUnreadOut(BaseModel):
    count: int
