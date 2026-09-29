"""Per-exercise progress and the learner's XP."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class ExerciseProgress(IdMixin, TimestampMixin, Base):
    __tablename__ = "exercise_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_id", name="uq_exercise_progress_user_exercise"),
        CheckConstraint("status in ('started', 'completed')", name="ck_exercise_progress_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(default="started")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    best_wpm: Mapped[int | None] = mapped_column(Integer)
    best_accuracy: Mapped[int | None] = mapped_column(Integer)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserStats(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date)
