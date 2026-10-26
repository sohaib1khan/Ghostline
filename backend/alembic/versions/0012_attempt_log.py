"""Mistake journal attempt log (90-day retention)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_attempt_log"
down_revision: str | None = "0011_spaced_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attempt_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("submitted", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("failed_rule_hint", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "source in ('lesson', 'review', 'game', 'boss')",
            name="ck_attempt_log_source",
        ),
    )
    op.create_index("ix_attempt_log_user_created", "attempt_log", ["user_id", "created_at"])
    op.create_index("ix_attempt_log_exercise", "attempt_log", ["exercise_id"])


def downgrade() -> None:
    op.drop_index("ix_attempt_log_exercise", table_name="attempt_log")
    op.drop_index("ix_attempt_log_user_created", table_name="attempt_log")
    op.drop_table("attempt_log")
