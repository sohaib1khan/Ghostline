"""Ghostwalk levels and per-user progress."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class GhostwalkLevel(IdMixin, TimestampMixin, Base):
    __tablename__ = "ghostwalk_levels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_ghostwalk_levels_slug"),
        CheckConstraint("mode in ('guided', 'free')", name="ck_ghostwalk_levels_mode"),
        CheckConstraint("status in ('draft', 'published')", name="ck_ghostwalk_levels_status"),
        CheckConstraint("par_lines >= 1", name="ck_ghostwalk_levels_par"),
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    concept: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    intro_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    grid: Mapped[list] = mapped_column(JSONB, nullable=False)
    start: Mapped[dict] = mapped_column(JSONB, nullable=False)
    allowed: Mapped[list] = mapped_column(JSONB, nullable=False)
    goal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    starter_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    solution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    par_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    python_lesson_slug: Mapped[str | None] = mapped_column(String(120))


class GhostwalkProgress(IdMixin, TimestampMixin, Base):
    __tablename__ = "ghostwalk_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "level_id", name="uq_ghostwalk_progress_user_level"),
        CheckConstraint(
            "status in ('started', 'completed')",
            name="ck_ghostwalk_progress_status",
        ),
        CheckConstraint("stars >= 0 AND stars <= 3", name="ck_ghostwalk_progress_stars"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ghostwalk_levels.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_lines: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
