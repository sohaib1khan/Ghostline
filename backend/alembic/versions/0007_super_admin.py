"""Add super_admin and promote the first approved admin."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_super_admin"
down_revision: str | None = "0006_practice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role in ('super_admin', 'admin', 'learner')",
    )
    # The earliest approved admin becomes the sole super admin for this install.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'super_admin'
            WHERE id = (
                SELECT id
                FROM users
                WHERE role = 'admin' AND status = 'approved'
                ORDER BY created_at ASC
                LIMIT 1
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'super_admin'"))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role in ('admin', 'learner')",
    )
