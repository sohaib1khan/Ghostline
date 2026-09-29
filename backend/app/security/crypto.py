"""Fernet encryption for secrets stored in the database."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import INSECURE_SECRET_VALUES, MIN_SECRET_LENGTH, get_settings


class SecretError(Exception):
    """The encryption key is unusable or the ciphertext is not ours."""


def _fernet(key: str | None = None) -> Fernet:
    raw = (key if key is not None else get_settings().app_encryption_key).strip()
    if raw.lower() in INSECURE_SECRET_VALUES or len(raw) < MIN_SECRET_LENGTH:
        raise SecretError("APP_ENCRYPTION_KEY is not a valid Fernet key")
    try:
        return Fernet(raw.encode())
    except (ValueError, TypeError):
        # DECISION: Fernet.generate_key() is the documented format. A long random
        # secret is accepted too and stretched with SHA-256, so a host that set
        # APP_ENCRYPTION_KEY the same way as APP_SECRET_KEY can still encrypt.
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        return Fernet(derived)


def encrypt_secret(plaintext: str, key: str | None = None) -> str:
    return _fernet(key).encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str, key: str | None = None) -> str:
    try:
        return _fernet(key).decrypt(ciphertext.encode()).decode()
    except SecretError:
        raise
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretError("Could not decrypt the stored secret") from exc
