import pytest
from app.security.passwords import hash_password, validate_password, verify_password


def test_hash_is_not_the_password() -> None:
    password = "correct-horse-battery"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed)
    assert not verify_password("correct-horse-batteries", hashed)


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="12 characters"):
        validate_password("short-pass")


def test_common_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="too common"):
        validate_password("password1234")


def test_password_matching_email_is_rejected() -> None:
    with pytest.raises(ValueError, match="too common"):
        validate_password("ada@example.com", email="ada@example.com")
