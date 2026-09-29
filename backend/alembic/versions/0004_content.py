"""Create modules, lessons, exercises, and content revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_content"
down_revision: str | None = "0003_notifications"
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
        "modules",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("track_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status in ('draft', 'published')", name="ck_modules_status"),
    )
    op.create_index("ix_modules_track_id", "modules", ["track_id"])
    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("module_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="original"),
        sa.Column("source_attribution", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("license_note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status in ('draft', 'review', 'published')",
            name="ck_lessons_status",
        ),
        sa.CheckConstraint(
            "source_type in ('original', 'adapted', 'ai_generated')",
            name="ck_lessons_source_type",
        ),
    )
    op.create_index("ix_lessons_module_id", "lessons", ["module_id"])
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("lesson_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "type in ('trace', 'fill', 'recall', 'challenge')",
            name="ck_exercises_type",
        ),
        sa.CheckConstraint("status in ('draft', 'published')", name="ck_exercises_status"),
    )
    op.create_index("ix_exercises_lesson_id", "exercises", ["lesson_id"])
    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("edited_by", sa.Uuid(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_content_revisions_entity_id", "content_revisions", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_content_revisions_entity_id", table_name="content_revisions")
    op.drop_table("content_revisions")
    op.drop_index("ix_exercises_lesson_id", table_name="exercises")
    op.drop_table("exercises")
    op.drop_index("ix_lessons_module_id", table_name="lessons")
    op.drop_table("lessons")
    op.drop_index("ix_modules_track_id", table_name="modules")
    op.drop_table("modules")
