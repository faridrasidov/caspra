# app/schemas/device_auth.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.management import HeartbeatStatus


class DeviceHandshakeRequest(BaseModel):
    """Unauthenticated bootstrap: a device announces itself to the server."""

    model_config = ConfigDict(extra="forbid")

    device_id: UUID
    serial: str | None = Field(None, max_length=120)
    firmware_version: str | None = Field(None, max_length=50)


class DeviceHandshakeOut(BaseModel):
    device_id: UUID
    registered: bool
    hmac_required: bool = True
    server_time: datetime


class DeviceTokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class DeviceRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)


class DeviceHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HeartbeatStatus = HeartbeatStatus.ONLINE
    uptime_s: int | None = Field(None, ge=0)


class DeviceHeartbeatOut(BaseModel):
    device_id: UUID
    status: HeartbeatStatus
    last_seen: datetime
    server_time: datetime


class DeviceConfigDownloadOut(BaseModel):
    device_id: UUID
    config: dict
