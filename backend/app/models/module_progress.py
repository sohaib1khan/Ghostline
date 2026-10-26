"""Per-module unlock and boss mastery."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class ModuleProgress(IdMixin, TimestampMixin, Base):
    __tablename__ = "module_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "module_id", name="uq_module_progress_user_module"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    unlocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlocked_by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    boss_score: Mapped[int | None] = mapped_column(Integer)
    boss_attempts: Mapped[int] = mapped_column(Integer, default=0)
