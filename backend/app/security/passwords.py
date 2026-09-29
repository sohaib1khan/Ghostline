"""Argon2id password hashing and a small common-password check."""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 200

# Long enough to pass the length rule, so the common-password check still matters.
COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "1q2w3e4r5t6y",
        "1qaz2wsx3edc",
        "abc123456789",
        "access123456",
        "admin1234567",
        "ashley123456",
        "asdfghjkl123",
        "bailey123456",
        "baseball1234",
        "batman123456",
        "changeme1234",
        "computer1234",
        "dragon123456",
        "football1234",
        "ghostline123",
        "iloveyou1234",
        "internet1234",
        "letmein12345",
        "master123456",
        "michael12345",
        "monkey123456",
        "passw0rd1234",
        "password1234",
        "password12345",
        "passwordpassword",
        "princess1234",
        "qwerty123456",
        "qwertyuiop12",
        "qwertyuiopas",
        "shadow123456",
        "starwars1234",
        "sunshine1234",
        "superman1234",
        "trustno11234",
        "welcome12345",
        "whatever1234",
        "zxcvbnm12345",
    }
)

# DECISION: Argon2id with the library defaults (time=3, memory=64 MiB).
_hasher = PasswordHash((Argon2Hasher(),))
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def dummy_password_hash() -> str:
    """A stable hash so a missing account takes about as long as a real check."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    return _dummy_hash


def validate_password(password: str, email: str | None = None) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Password must be at least 12 characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password is too long")
    folded = password.casefold()
    if folded in COMMON_PASSWORDS or (email and folded == email.casefold()):
        raise ValueError("Password is too common")
