"""Public display aliases for privacy on shared boards."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_public_alias"
down_revision: str | None = "0016_tickets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADJECTIVES = (
    "Async",
    "Binary",
    "Cached",
    "Compiled",
    "Cryptic",
    "Debugged",
    "Fuzzy",
    "Immutable",
    "Indexed",
    "Lambda",
    "Nested",
    "Null",
    "Parallel",
    "Pixel",
    "Quantum",
    "Recursive",
    "Regex",
    "Sneaky",
    "Stacked",
    "Typed",
    "Virtual",
    "Wired",
)
NOUNS = (
    "Alpaca",
    "Badger",
    "Beaver",
    "Buffer",
    "Byte",
    "Cactus",
    "Compiler",
    "Falcon",
    "Gopher",
    "Kernel",
    "Koala",
    "Llama",
    "Otter",
    "Packet",
    "Panda",
    "Pointer",
    "Python",
    "Raccoon",
    "Sprite",
    "Stack",
    "Turtle",
    "Walrus",
)


def _invent(index: int) -> str:
    adj = ADJECTIVES[index % len(ADJECTIVES)]
    noun = NOUNS[(index * 7) % len(NOUNS)]
    base = f"{adj} {noun}"
    # Keep collisions rare across backfill by suffixing when needed.
    return base if index < len(ADJECTIVES) * len(NOUNS) else f"{base} {index}"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("public_alias", sa.String(length=40), nullable=False, server_default=""),
    )
    conn = op.get_bind()
    rows = list(conn.execute(sa.text("SELECT id FROM users ORDER BY created_at ASC")).fetchall())
    used: set[str] = set()
    for index, row in enumerate(rows):
        alias = _invent(index)
        n = 0
        while alias.lower() in used:
            n += 1
            alias = f"{_invent(index)} {n}"
            if len(alias) > 40:
                alias = alias[:40].rstrip()
        used.add(alias.lower())
        conn.execute(
            sa.text("UPDATE users SET public_alias = :alias WHERE id = :id"),
            {"alias": alias, "id": row[0]},
        )
    op.create_index("ix_users_public_alias", "users", ["public_alias"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_public_alias", table_name="users")
    op.drop_column("users", "public_alias")
