"""Practice events for stats, games, and the leaderboard."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_practice"
down_revision: str | None = "0005_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("exercise_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("wpm", sa.Integer(), nullable=True),
        sa.Column("accuracy", sa.Integer(), nullable=True),
        sa.Column("xp_awarded", sa.Integer(), nullable=False, server_default="0"),
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
            "source in ('lesson', 'speed_drill', 'bug_hunt', 'command_roulette', 'fill_frenzy')",
            name="ck_practice_events_source",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_practice_events_user_id", "practice_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_events_user_id", table_name="practice_events")
    op.drop_table("practice_events")
