"""Ghostwalk languages and farm mode."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_ghostwalk_languages"
down_revision: str | None = "0014_ghostwalk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANGS = ("python", "javascript", "bash", "go", "sql", "csharp", "java")


def upgrade() -> None:
    op.add_column(
        "ghostwalk_levels",
        sa.Column("language", sa.String(length=20), nullable=False, server_default="python"),
    )
    op.create_check_constraint(
        "ck_ghostwalk_levels_language",
        "ghostwalk_levels",
        "language in ('python', 'javascript', 'bash', 'go', 'sql', 'csharp', 'java')",
    )
    op.create_index("ix_ghostwalk_levels_language", "ghostwalk_levels", ["language"])

    op.drop_constraint("ck_ghostwalk_levels_mode", "ghostwalk_levels", type_="check")
    op.create_check_constraint(
        "ck_ghostwalk_levels_mode",
        "ghostwalk_levels",
        "mode in ('guided', 'free', 'farm')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ghostwalk_levels_mode", "ghostwalk_levels", type_="check")
    op.create_check_constraint(
        "ck_ghostwalk_levels_mode",
        "ghostwalk_levels",
        "mode in ('guided', 'free')",
    )
    op.drop_index("ix_ghostwalk_levels_language", table_name="ghostwalk_levels")
    op.drop_constraint("ck_ghostwalk_levels_language", "ghostwalk_levels", type_="check")
    op.drop_column("ghostwalk_levels", "language")
