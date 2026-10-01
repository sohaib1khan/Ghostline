"""One scored pass from a lesson or a game, used for trends."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin

SOURCES = ("lesson", "speed_drill", "bug_hunt", "command_roulette", "fill_frenzy")


class PracticeEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "practice_events"
    __table_args__ = (
        CheckConstraint(
            "source in ('lesson', 'speed_drill', 'bug_hunt', 'command_roulette', 'fill_frenzy')",
            name="ck_practice_events_source",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    wpm: Mapped[int | None] = mapped_column(Integer)
    accuracy: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
