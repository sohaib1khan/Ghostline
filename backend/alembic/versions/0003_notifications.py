"""Create notification channels."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_notifications"
down_revision: str | None = "0002_tracks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider in ('resend', 'smtp', 'gotify', 'slack', 'discord', 'ntfy', 'webhook')",
            name="ck_notification_channels_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_channels")
