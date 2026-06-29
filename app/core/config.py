# app/core/config.py

from functools import lru_cache

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
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    device_hmac_secret: str = Field(default="change-me-device-secret")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Database URL used by Alembic and the async engine."""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
