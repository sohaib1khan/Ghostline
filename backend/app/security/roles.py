"""Privileged account roles."""

from __future__ import annotations

# Studio / site tools are super_admin only. Everyone else is a learner.
STAFF_ROLES = frozenset({"super_admin"})
SUPER_ADMIN_ROLE = "super_admin"
ASSIGNABLE_ROLES = frozenset({"learner"})


def is_staff(role: str) -> bool:
    return role in STAFF_ROLES


def is_super_admin(role: str) -> bool:
    return role == SUPER_ADMIN_ROLE
