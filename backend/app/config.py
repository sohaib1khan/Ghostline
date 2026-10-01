"""Settings loaded from the environment."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values shipped in .env.example. They are fine for local development and
# must never be used when APP_ENV=production.
INSECURE_SECRET_VALUES = frozenset({"", "change-me", "changeme"})
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost:8080"
    app_secret_key: str = "change-me"
    app_encryption_key: str = "change-me"
    session_ttl_hours: int = Field(default=168, ge=1, le=24 * 30)
    database_url: str = "postgresql+asyncpg://ghostline:change-me@db:5432/ghostline"
    web_port: int = Field(default=8080, ge=1, le=65535)
    rate_limit_login: int = Field(default=5, ge=1)
    rate_limit_signup: int = Field(default=3, ge=1)
    rate_limit_demo_check: int = Field(default=30, ge=1)
    # DECISION: AI calls can spend a provider quota, so they have their own cap.
    rate_limit_ai: int = Field(default=10, ge=1)
    # Ephemeral playground workers (Docker). Off unless explicitly enabled.
    playground_enabled: bool = False
    playground_url: str = "http://playground:8100"
    playground_token: str = ""
    # Fixed 12-hour playground lifetime; extend resets another full window.
    playground_ttl_min_minutes: int = Field(default=720, ge=1, le=720)
    playground_ttl_max_minutes: int = Field(default=720, ge=1, le=720)
    playground_ttl_default_minutes: int = Field(default=720, ge=1, le=720)
    playground_memory_mb: int = Field(default=256, ge=64, le=1024)
    playground_run_timeout_seconds: int = Field(default=8, ge=1, le=60)
    # One-shot first admin. Ignored once any admin exists.
    bootstrap_allow: bool = False
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_first_name: str = "Admin"
    bootstrap_admin_last_name: str = "User"

    @field_validator("app_env")
    @classmethod
    def env_must_be_known(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "production"}:
            raise ValueError("APP_ENV must be development or production")
        return normalized

    @field_validator("app_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    def assert_production_secrets(self) -> None:
        """Refuse to boot in production with missing or example secrets.

        # DECISION: development and tests may use the .env.example placeholders
        # so a fresh clone can boot. Production must set unique values.
        """
        if self.app_env != "production":
            return
        problems: list[str] = []
        if not _secret_is_strong(self.app_secret_key):
            problems.append("APP_SECRET_KEY")
        if not _secret_is_strong(self.app_encryption_key):
            problems.append("APP_ENCRYPTION_KEY")
        if "change-me" in self.database_url or "changeme" in self.database_url:
            problems.append("DATABASE_URL")
        if problems:
            names = ", ".join(problems)
            raise RuntimeError(f"Refusing to start in production with insecure settings: {names}")


def _secret_is_strong(value: str) -> bool:
    stripped = value.strip()
    if stripped.lower() in INSECURE_SECRET_VALUES:
        return False
    return len(stripped) >= MIN_SECRET_LENGTH


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.assert_production_secrets()
    return settings
