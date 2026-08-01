# app/core/config.py

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Caspra API"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    admin_api_prefix: str = "/admin/api/v1"
    device_api_prefix: str = "/device/api/v1"
    public_api_prefix: str = "/public/api/v1"

    public_rate_limit_per_minute: int = 600

    database_url: str = Field(
        default="postgresql+asyncpg://caspra:caspra@localhost:5432/caspra",
        description="Async SQLAlchemy database URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0")

    testing: bool = False

    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 15
    algorithm: str = "HS256"
    refresh_cookie_name: str = "caspra_refresh"
    login_rate_limit_per_minute: int = Field(default=5, ge=1, le=100)

    device_hmac_secret: str = Field(default="change-me-device-secret")
    device_secret_encryption_key: str = Field(default="change-me-device-encryption-key")
    device_hmac_v1_enabled: bool = True
    device_hmac_v1_sunset_at: datetime | None = None
    device_signature_max_age_seconds: int = Field(default=300, ge=30, le=3600)
    device_previous_secret_grace_seconds: int = Field(default=86400, ge=0, le=2592000)
    firmware_signing_secret: str = Field(default="change-me-firmware-signing-secret")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Database URL used by Alembic and the async engine."""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_runtime_settings(current: Settings = settings) -> None:
    """Reject unsafe production configuration before the API starts."""
    if current.testing or current.environment != "production":
        return

    unsafe_values = {
        "SECRET_KEY": (current.secret_key, "change-me-in-production"),
        "DEVICE_HMAC_SECRET": (current.device_hmac_secret, "change-me-device-secret"),
        "DEVICE_SECRET_ENCRYPTION_KEY": (
            current.device_secret_encryption_key,
            "change-me-device-encryption-key",
        ),
        "FIRMWARE_SIGNING_SECRET": (
            current.firmware_signing_secret,
            "change-me-firmware-signing-secret",
        ),
    }
    unsafe_names = [name for name, (value, default) in unsafe_values.items() if value == default]
    if unsafe_names:
        joined = ", ".join(unsafe_names)
        raise RuntimeError(f"Unsafe production secrets: {joined}")
    if current.debug:
        raise RuntimeError("DEBUG must be false in production")
    if "*" in current.cors_origins:
        raise RuntimeError("Wildcard CORS origins are not allowed in production")
    if current.device_hmac_v1_enabled:
        sunset = current.device_hmac_v1_sunset_at
        now = datetime.now(UTC)
        if sunset is None:
            raise RuntimeError("DEVICE_HMAC_V1_SUNSET_AT is required while HMAC v1 is enabled")
        if sunset <= now or sunset > now + timedelta(days=30):
            raise RuntimeError("HMAC v1 sunset must be within the next 30 days")
