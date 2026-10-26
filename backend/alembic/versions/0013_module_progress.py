"""Module unlock and mastery tracking for ladder gating."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_module_progress"
down_revision: str | None = "0012_attempt_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "module_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("module_id", sa.Uuid(), nullable=False),
        sa.Column("unlocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unlocked_by_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("boss_score", sa.Integer(), nullable=True),
        sa.Column("boss_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "module_id", name="uq_module_progress_user_module"),
    )
    op.create_index("ix_module_progress_user", "module_progress", ["user_id"])
    # Grandfather: unlock every module where the learner already has any exercise progress.
    op.execute(
        """
        INSERT INTO module_progress (id, created_at, updated_at, user_id, module_id, unlocked, unlocked_by_admin, boss_attempts)
        SELECT gen_random_uuid(), now(), now(), ep.user_id, l.module_id, true, false, 0
        FROM exercise_progress ep
        JOIN exercises e ON e.id = ep.exercise_id
        JOIN lessons l ON l.id = e.lesson_id
        GROUP BY ep.user_id, l.module_id
        ON CONFLICT (user_id, module_id) DO NOTHING
        """
    )
    # First published module of each track is always unlocked for every user with track access.
    op.execute(
        """
        INSERT INTO module_progress (id, created_at, updated_at, user_id, module_id, unlocked, unlocked_by_admin, boss_attempts)
        SELECT gen_random_uuid(), now(), now(), uta.user_id, first_mod.id, true, false, 0
        FROM user_track_access uta
        JOIN LATERAL (
            SELECT m.id
            FROM modules m
            WHERE m.track_id = uta.track_id AND m.status = 'published'
            ORDER BY m."order" ASC
            LIMIT 1
        ) first_mod ON true
        ON CONFLICT (user_id, module_id) DO UPDATE SET unlocked = true
        """
    )


def downgrade() -> None:
    op.drop_index("ix_module_progress_user", table_name="module_progress")
    op.drop_table("module_progress")
