"""Spaced review fields on exercise_progress."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_spaced_review"
down_revision: str | None = "0010_user_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exercise_progress",
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "exercise_progress",
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exercise_progress",
        sa.Column("ease", sa.Numeric(4, 2), nullable=False, server_default="2.50"),
    )
    op.add_column(
        "exercise_progress",
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exercise_progress",
        sa.Column("last_result", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_exercise_progress_next_review_at", "exercise_progress", ["next_review_at"])
    # Spread existing completions so nobody wakes up to hundreds of reviews.
    op.execute(
        """
        UPDATE exercise_progress
        SET next_review_at = completed_at + ((ABS(HASHTEXT(exercise_id::text)) % 7) + 1) * INTERVAL '1 day',
            interval_days = 1,
            ease = 2.50,
            last_result = 'pass'
        WHERE status = 'completed' AND completed_at IS NOT NULL AND next_review_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_exercise_progress_next_review_at", table_name="exercise_progress")
    op.drop_column("exercise_progress", "last_result")
    op.drop_column("exercise_progress", "lapses")
    op.drop_column("exercise_progress", "ease")
    op.drop_column("exercise_progress", "interval_days")
    op.drop_column("exercise_progress", "next_review_at")
