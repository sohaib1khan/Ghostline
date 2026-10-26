"""Mistake journal helpers."""

from app.services.journal import RETENTION_DAYS


def test_retention_is_ninety_days() -> None:
    assert RETENTION_DAYS == 90
