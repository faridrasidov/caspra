from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings, validate_runtime_settings


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "testing": False,
        "debug": False,
        "secret_key": "production-secret",
        "device_hmac_secret": "migration-only-device-secret",
        "device_secret_encryption_key": "production-encryption-key",
        "firmware_signing_secret": "production-firmware-key",
        "device_hmac_v1_enabled": False,
        "cors_origins": ["https://operator.example.test"],
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_default_secrets():
    with pytest.raises(RuntimeError, match="Unsafe production secrets"):
        validate_runtime_settings(
            production_settings(
                secret_key="change-me-in-production",
                device_hmac_secret="change-me-device-secret",
            )
        )


def test_hmac_v1_requires_a_bounded_migration_window():
    with pytest.raises(RuntimeError, match="SUNSET_AT"):
        validate_runtime_settings(
            production_settings(
                device_hmac_v1_enabled=True,
                device_hmac_v1_sunset_at=None,
            )
        )

    validate_runtime_settings(
        production_settings(
            device_hmac_v1_enabled=True,
            device_hmac_v1_sunset_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
