import pytest
from app.security.crypto import SecretError, decrypt_secret, encrypt_secret
from cryptography.fernet import Fernet


def test_round_trip() -> None:
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_secret("notify-key", key=key)
    assert ciphertext != "notify-key"
    assert decrypt_secret(ciphertext, key=key) == "notify-key"


def test_long_secret_round_trips() -> None:
    key = "x" * 40
    ciphertext = encrypt_secret("notify-key", key=key)
    assert ciphertext != "notify-key"
    assert decrypt_secret(ciphertext, key=key) == "notify-key"


def test_invalid_key_is_rejected() -> None:
    with pytest.raises(SecretError):
        encrypt_secret("notify-key", key="change-me")


def test_tampered_ciphertext_is_rejected() -> None:
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_secret("notify-key", key=key)
    last = "A" if ciphertext[-1] != "A" else "B"
    with pytest.raises(SecretError):
        decrypt_secret(ciphertext[:-1] + last, key=key)
