# app/api/device/endpoints/ws.py

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import verify_device_signature
from app.models.device.device import Device, DeviceStatus

router = APIRouter()

WS_POLICY_VIOLATION = 1008


@router.websocket("/ws")
async def device_ws(websocket: WebSocket) -> None:
    """Real-time device↔server sync channel.

    The device authenticates on connect via signed query params
    (``device_id``, ``timestamp``, ``signature``) using the same HMAC scheme as
    the REST surface (empty body). The socket then relays simple JSON messages.
    """
    device_id = websocket.query_params.get("device_id")
    timestamp = websocket.query_params.get("timestamp")
    signature = websocket.query_params.get("signature")

    if not device_id or not timestamp or not signature:
        await websocket.close(code=WS_POLICY_VIOLATION)
        return
    if not verify_device_signature(device_id, timestamp, b"", signature):
        await websocket.close(code=WS_POLICY_VIOLATION)
        return

    try:
        device_uuid = UUID(device_id)
    except (ValueError, TypeError):
        await websocket.close(code=WS_POLICY_VIOLATION)
        return

    session_factory = websocket.app.state.session_factory
    async with session_factory() as session:
        device = await session.get(Device, device_uuid)
        if device is None or device.status != DeviceStatus.ACTIVE.value:
            await websocket.close(code=WS_POLICY_VIOLATION)
            return

    await websocket.accept()
    await websocket.send_json(
        {"type": "connected", "device_id": device_id, "server_time": datetime.now(UTC).isoformat()}
    )
    try:
        while True:
            message = await websocket.receive_json()
            await websocket.send_json(
                {
                    "type": "ack",
                    "received": message,
                    "server_time": datetime.now(UTC).isoformat(),
                }
            )
    except WebSocketDisconnect:
        return
