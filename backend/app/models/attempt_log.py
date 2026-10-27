"""Per-attempt mistake journal entries."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class AttemptLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "attempt_log"
    __table_args__ = (
        CheckConstraint(
            "source in ('lesson', 'review', 'game', 'boss', 'ghostwalk')",
            name="ck_attempt_log_source",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=True
    )
    submitted: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failed_rule_hint: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
