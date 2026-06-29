# app/models/device/device.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import JSON, VARCHAR, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CardStatus(enum.StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    LOST = "lost"


class CardType(enum.StrEnum):
    RFID = "rfid"
    NFC = "nfc"
    WRISTBAND = "wristband"


class DeviceStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class DeviceType(enum.StrEnum):
    READER = "reader"
    POS = "pos"


class DeviceEventLevel(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class KioskStatus(enum.StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Card(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """RFID/NFC/wristband card, optionally assigned to a customer."""

    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("tenant_id", "uid", name="uq_cards_tenant_uid"),)

    uid: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, index=True)
    type: Mapped[CardType] = mapped_column(VARCHAR(20), nullable=False, default=CardType.RFID.value)
    status: Mapped[CardStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=CardStatus.ACTIVE.value
    )
    customer_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", name="fk_cards_customer_id_customers", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class Device(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A reader or POS terminal at a location."""

    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    serial: Mapped[str | None] = mapped_column(VARCHAR(120), nullable=True, index=True)
    type: Mapped[DeviceType] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceType.READER.value
    )
    status: Mapped[DeviceStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceStatus.ACTIVE.value
    )
    location_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", name="fk_devices_location_id_locations", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class DeviceConfig(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-device configuration payload."""

    __tablename__ = "device_configs"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_configs_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class DeviceEvent(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Telemetry/event emitted by a device."""

    __tablename__ = "device_events"

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_device_events_device_id_devices", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(VARCHAR(80), nullable=False)
    level: Mapped[DeviceEventLevel] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceEventLevel.INFO.value
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Kiosk(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Self-service kiosk at a location."""

    __tablename__ = "kiosks"

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    status: Mapped[KioskStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=KioskStatus.OFFLINE.value
    )
    location_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", name="fk_kiosks_location_id_locations", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class KioskLog(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Log line emitted by a kiosk."""

    __tablename__ = "kiosk_logs"

    kiosk_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", name="fk_kiosk_logs_kiosk_id_kiosks", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[DeviceEventLevel] = mapped_column(
        VARCHAR(20), nullable=False, default=DeviceEventLevel.INFO.value
    )
    message: Mapped[str] = mapped_column(VARCHAR(2000), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
