"""Opaque session tokens. Only the SHA-256 hash is stored."""

import hashlib
import secrets


def new_token() -> str:
    # 32 bytes is 256 bits of randomness.
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), token_hash)
