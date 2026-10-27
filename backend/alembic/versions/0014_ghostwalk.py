"""Ghostwalk levels and progress tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_ghostwalk"
down_revision: str | None = "0013_module_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Allow journal rows that are not tied to a lesson exercise (Ghostwalk).
    op.alter_column("attempt_log", "exercise_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint("ck_attempt_log_source", "attempt_log", type_="check")
    op.create_check_constraint(
        "ck_attempt_log_source",
        "attempt_log",
        "source in ('lesson', 'review', 'game', 'boss', 'ghostwalk')",
    )

    op.create_table(
        "ghostwalk_levels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("concept", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("intro_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("grid", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("start", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("goal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="free"),
        sa.Column("starter_code", sa.Text(), nullable=False, server_default=""),
        sa.Column("solution", sa.Text(), nullable=False, server_default=""),
        sa.Column("hints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("par_lines", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("python_lesson_slug", sa.String(length=120), nullable=True),
        sa.CheckConstraint("mode in ('guided', 'free')", name="ck_ghostwalk_levels_mode"),
        sa.CheckConstraint("status in ('draft', 'published')", name="ck_ghostwalk_levels_status"),
        sa.CheckConstraint("par_lines >= 1", name="ck_ghostwalk_levels_par"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_ghostwalk_levels_slug"),
    )
    op.create_index("ix_ghostwalk_levels_position", "ghostwalk_levels", ["position"])

    op.create_table(
        "ghostwalk_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_lines", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["level_id"], ["ghostwalk_levels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "level_id", name="uq_ghostwalk_progress_user_level"),
        sa.CheckConstraint("status in ('started', 'completed')", name="ck_ghostwalk_progress_status"),
        sa.CheckConstraint("stars >= 0 AND stars <= 3", name="ck_ghostwalk_progress_stars"),
    )
    op.create_index("ix_ghostwalk_progress_user", "ghostwalk_progress", ["user_id"])
    op.create_index("ix_ghostwalk_progress_review", "ghostwalk_progress", ["next_review_at"])


def downgrade() -> None:
    op.drop_index("ix_ghostwalk_progress_review", table_name="ghostwalk_progress")
    op.drop_index("ix_ghostwalk_progress_user", table_name="ghostwalk_progress")
    op.drop_table("ghostwalk_progress")
    op.drop_index("ix_ghostwalk_levels_position", table_name="ghostwalk_levels")
    op.drop_table("ghostwalk_levels")
    op.drop_constraint("ck_attempt_log_source", "attempt_log", type_="check")
    op.create_check_constraint(
        "ck_attempt_log_source",
        "attempt_log",
        "source in ('lesson', 'review', 'game', 'boss')",
    )
    op.alter_column("attempt_log", "exercise_id", existing_type=sa.Uuid(), nullable=False)
