"""Record typing duration on practice events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_practice_duration"
down_revision: str | None = "0007_super_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_events",
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_events", "duration_seconds")
