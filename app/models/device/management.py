# app/models/device/management.py

from datetime import datetime
import enum
from uuid import UUID as PyUUID

from sqlalchemy import (
    JSON,
    VARCHAR,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceTokenType(enum.StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class FirmwareUpdateStatus(enum.StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"


class DeviceCommandType(enum.StrEnum):
    RESTART = "restart"
    CONFIG_RESET = "config_reset"
    RELOAD = "reload"
    FIRMWARE_UPDATE = "firmware_update"
    SYNC = "sync"
    MESSAGE = "message"


class DeviceCommandStatus(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKED = "acked"
    FAILED = "failed"


class HeartbeatStatus(enum.StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class DeviceToken(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Hashed device-access / refresh token issued to a reader after login."""

    __tablename__ = "device_tokens"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_tokens_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, unique=True, index=True)
    type: Mapped[DeviceTokenType] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceTokenType.ACCESS.value
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Firmware(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A firmware image available for a target device type."""

    __tablename__ = "firmwares"

    version: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    target_device_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    binary_url: Mapped[str] = mapped_column(VARCHAR(1000), nullable=False)
    checksum: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FirmwareUpdate(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-device firmware update job and its progress."""

    __tablename__ = "firmware_updates"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_firmware_updates_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    firmware_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "firmwares.id", name="fk_firmware_updates_firmware_id_firmwares", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[FirmwareUpdateStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=FirmwareUpdateStatus.PENDING.value
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)


class DeviceCommand(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Server→device command queued for the device to pull and execute."""

    __tablename__ = "device_commands"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_commands_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[DeviceCommandType] = mapped_column(VARCHAR(30), nullable=False)
    status: Mapped[DeviceCommandStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceCommandStatus.PENDING.value
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DeviceTelemetry(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A telemetry sample pushed by a device (non-monetary metrics)."""

    __tablename__ = "device_telemetry"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_telemetry_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_s: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeviceHeartbeat(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Last-seen heartbeat row for a device."""

    __tablename__ = "device_heartbeats"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_heartbeats_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[HeartbeatStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=HeartbeatStatus.ONLINE.value
    )
