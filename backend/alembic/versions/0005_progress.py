"""Record exercise progress, XP, and streaks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_progress"
down_revision: str | None = "0004_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "exercise_progress",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("exercise_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_wpm", sa.Integer(), nullable=True),
        sa.Column("best_accuracy", sa.Integer(), nullable=True),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "exercise_id", name="uq_exercise_progress_user_exercise"),
        sa.CheckConstraint(
            "status in ('started', 'completed')",
            name="ck_exercise_progress_status",
        ),
    )
    op.create_index("ix_exercise_progress_user_id", "exercise_progress", ["user_id"])
    op.create_table(
        "user_stats",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_stats_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_stats")
    op.drop_index("ix_exercise_progress_user_id", table_name="exercise_progress")
    op.drop_table("exercise_progress")
