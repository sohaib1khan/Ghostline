"""Public alias generation and validation."""

import pytest
from app.services.aliases import clean_alias, invent_alias


def test_invent_alias_is_two_words() -> None:
    alias = invent_alias()
    parts = alias.split()
    assert len(parts) == 2
    assert parts[0][0].isupper()
    assert parts[1][0].isupper()


def test_clean_alias_rejects_symbols() -> None:
    with pytest.raises(ValueError):
        clean_alias("null@pointer")


def test_clean_alias_keeps_spaces() -> None:
    assert clean_alias("  Recursive   Raccoon ") == "Recursive Raccoon"
