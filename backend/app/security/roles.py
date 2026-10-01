"""Privileged account roles."""

from __future__ import annotations

STAFF_ROLES = frozenset({"super_admin", "admin"})
SUPER_ADMIN_ROLE = "super_admin"
ASSIGNABLE_ROLES = frozenset({"admin", "learner"})


def is_staff(role: str) -> bool:
    return role in STAFF_ROLES


def is_super_admin(role: str) -> bool:
    return role == SUPER_ADMIN_ROLE
