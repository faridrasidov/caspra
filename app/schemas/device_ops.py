# app/schemas/device_ops.py

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import DeviceEventLevel
from app.models.device.management import (
    DeviceCommandStatus,
    DeviceCommandType,
    FirmwareUpdateStatus,
)

# ========== Events ==========


class DeviceEventPushItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1, max_length=80)
    level: DeviceEventLevel = DeviceEventLevel.INFO
    payload: dict | None = None


class DeviceEventPushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[DeviceEventPushItem] = Field(..., max_length=200)


class DeviceEventPushOut(BaseModel):
    accepted: int


class DeviceCommandOut(BaseModel):
    id: UUID
    type: DeviceCommandType
    status: DeviceCommandStatus
    payload: dict | None = None
    lease_expires_at: datetime | None = None
    delivery_attempts: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceCommandPullOut(BaseModel):
    commands: list[DeviceCommandOut]


class DeviceCommandAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["acked", "failed"]
    error: str | None = Field(None, max_length=500)


# ========== Settings ==========


class DeviceSettingsOut(BaseModel):
    device_id: UUID
    config: dict


class DeviceSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict


class DeviceReloadOut(BaseModel):
    command_id: UUID
    status: DeviceCommandStatus


# ========== Firmware ==========


class FirmwareInfo(BaseModel):
    id: UUID
    version: str
    checksum: str
    size_bytes: int | None = None

    model_config = ConfigDict(from_attributes=True)


class FirmwareCheckOut(BaseModel):
    update_available: bool
    firmware: FirmwareInfo | None = None


class FirmwareDownloadOut(BaseModel):
    firmware_id: UUID
    version: str
    download_url: str
    checksum: str
    size_bytes: int | None = None
    expires_at: datetime


class FirmwareUpdateStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    firmware_id: UUID
    status: FirmwareUpdateStatus
    progress: int = Field(0, ge=0, le=100)
    error: str | None = Field(None, max_length=500)


class FirmwareUpdateOut(BaseModel):
    id: UUID
    firmware_id: UUID
    status: FirmwareUpdateStatus
    progress: int

    model_config = ConfigDict(from_attributes=True)


# ========== Sync / Telemetry ==========


class SyncStatusOut(BaseModel):
    device_id: UUID
    pending_commands: int
    last_seen: datetime | None = None
    server_time: datetime


class TelemetryPushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_percent: float | None = Field(None, ge=0)
    temperature_c: float | None = None
    uptime_s: int | None = Field(None, ge=0)


class TelemetryPushOut(BaseModel):
    id: UUID
    recorded: bool


# ========== Health / Ping / MQTT ==========


class PingOut(BaseModel):
    pong: bool = True
    server_time: datetime


class DeviceHealthOut(BaseModel):
    status: str = "ok"
    server_time: datetime


class MqttInfoOut(BaseModel):
    """Connection metadata stub for an external MQTT broker (not implemented here)."""

    broker_url: str
    port: int
    topic_prefix: str
    client_id: str
    keepalive_s: int
