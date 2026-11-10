"""Collapse roles to super_admin + learner; music settings use AppSetting JSON."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_roles_and_music"
down_revision: str | None = "0017_public_alias"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Former site admins become learners — Studio stays super_admin only.
    op.execute(sa.text("UPDATE users SET role = 'learner' WHERE role = 'admin'"))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role in ('super_admin', 'learner')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role in ('super_admin', 'admin', 'learner')",
    )
