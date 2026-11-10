"""Funny programming aliases for public display."""

from __future__ import annotations

import re
import secrets
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

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

ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 -]{1,38}[A-Za-z0-9]$")


def clean_alias(value: str) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        raise ValueError("Public alias is required")
    if len(cleaned) > 40:
        raise ValueError("Public alias is too long")
    if not ALIAS_RE.match(cleaned):
        raise ValueError(
            "Use letters, numbers, spaces, or hyphens — start with a letter"
        )
    return cleaned


def invent_alias() -> str:
    return f"{secrets.choice(ADJECTIVES)} {secrets.choice(NOUNS)}"


async def alias_taken(
    session: AsyncSession,
    alias: str,
    *,
    except_user_id: UUID | None = None,
) -> bool:
    stmt = select(User.id).where(func.lower(User.public_alias) == alias.lower())
    if except_user_id is not None:
        stmt = stmt.where(User.id != except_user_id)
    return await session.scalar(stmt) is not None


async def unique_alias(
    session: AsyncSession,
    *,
    except_user_id: UUID | None = None,
    preferred: str | None = None,
) -> str:
    if preferred:
        candidate = clean_alias(preferred)
        if not await alias_taken(session, candidate, except_user_id=except_user_id):
            return candidate
        raise ValueError("That public alias is already taken")
    for _ in range(40):
        candidate = invent_alias()
        if not await alias_taken(session, candidate, except_user_id=except_user_id):
            return candidate
    # Extremely unlikely collision storm — append a short suffix.
    for _ in range(20):
        candidate = f"{invent_alias()} {secrets.token_hex(1).upper()}"
        if len(candidate) <= 40 and not await alias_taken(
            session, candidate, except_user_id=except_user_id
        ):
            return candidate
    raise ValueError("Could not invent a free alias")


def public_label(user: User) -> str:
    alias = (user.public_alias or "").strip()
    return alias or "Anonymous Coder"


def real_label(user: User) -> str:
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email
