"""Admin-configured notification channels. The config column is ciphertext."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin

PROVIDERS = ("resend", "smtp", "gotify", "slack", "discord", "ntfy", "webhook")


class NotificationChannel(IdMixin, TimestampMixin, Base):
    __tablename__ = "notification_channels"
    __table_args__ = (
        CheckConstraint(
            "provider in ('resend', 'smtp', 'gotify', 'slack', 'discord', 'ntfy', 'webhook')",
            name="ck_notification_channels_provider",
        ),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    config_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
