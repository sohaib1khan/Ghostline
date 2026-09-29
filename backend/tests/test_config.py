import pytest
from app.config import Settings, get_settings
from pydantic import ValidationError

STRONG_SECRET = "x" * 48


def test_development_allows_example_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_SECRET_KEY", "change-me")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "change-me")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.app_env == "development"
    finally:
        get_settings.cache_clear()


def test_production_rejects_example_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "change-me")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "change-me")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ghostline:change-me@db:5432/ghostline")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_production_rejects_short_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "short-but-not-default")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", STRONG_SECRET)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ghostline:s3cret@db:5432/ghostline")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_production_accepts_strong_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", STRONG_SECRET)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "y" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ghostline:s3cret@db:5432/ghostline")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.app_env == "production"
    finally:
        get_settings.cache_clear()


def test_unknown_app_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_settings_model_strips_base_url() -> None:
    settings = Settings(app_base_url="http://localhost:8080/")
    assert settings.app_base_url == "http://localhost:8080"
