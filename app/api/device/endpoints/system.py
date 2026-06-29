# app/api/device/endpoints/system.py

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_ops import DeviceHealthOut, MqttInfoOut, PingOut

router = APIRouter(tags=["device-system"])


@router.get("/ping", response_model=PingOut)
async def ping() -> PingOut:
    """Lightweight unauthenticated liveness check for readers."""
    return PingOut(pong=True, server_time=datetime.now(UTC))


@router.get("/health", response_model=DeviceHealthOut)
async def health() -> DeviceHealthOut:
    """Lightweight unauthenticated health check for the device API surface."""
    return DeviceHealthOut(status="ok", server_time=datetime.now(UTC))


@router.get("/mqtt/info", response_model=MqttInfoOut)
async def mqtt_info(
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> MqttInfoOut:
    """Return MQTT broker connection metadata (stub — no broker is run here)."""
    return MqttInfoOut(
        broker_url="mqtt://localhost",
        port=1883,
        topic_prefix=f"devices/{device.tenant_id}/{device.id}",
        client_id=str(device.id),
        keepalive_s=60,
    )
