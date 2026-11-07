"""Bug report tickets and reply threads."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_tickets"
down_revision: str | None = "0015_ghostwalk_languages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("page_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("page_path", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=400), nullable=False, server_default=""),
        sa.Column("viewport", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("context_json", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=NOW,
            nullable=False,
        ),
        sa.Column(
            "unread_for_creator",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "unread_for_staff",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_tickets_public_id"),
        sa.CheckConstraint(
            "category in ("
            "'page_broken','check_failed','editor_typing','ghostwalk_games',"
            "'wrong_content','account_access','other'"
            ")",
            name="ck_tickets_category",
        ),
        sa.CheckConstraint(
            "status in ('open','waiting_on_user','resolved','closed')",
            name="ck_tickets_status",
        ),
    )
    op.create_index("ix_tickets_created_by_user_id", "tickets", ["created_by_user_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_last_message_at", "tickets", ["last_message_at"])
    op.create_index("ix_tickets_unread_for_staff", "tickets", ["unread_for_staff"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_from_staff",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    op.create_index("ix_ticket_messages_created_at", "ticket_messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
