# app/api/device/endpoints/auth.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_auth import (
    DeviceConfigDownloadOut,
    DeviceHandshakeOut,
    DeviceHandshakeRequest,
    DeviceHeartbeatOut,
    DeviceHeartbeatRequest,
    DeviceRefreshRequest,
    DeviceTokenOut,
)
from app.services.device_auth import DeviceAuthService

router = APIRouter(prefix="/auth", tags=["device-auth"])


@router.post("/handshake", response_model=DeviceHandshakeOut)
async def handshake(
    payload: DeviceHandshakeRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> DeviceHandshakeOut:
    """Unauthenticated bootstrap: report whether a device is registered/active."""
    try:
        return await DeviceAuthService().handshake(db, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Handshake failed: {e}",
        ) from e


@router.post("/login", response_model=DeviceTokenOut, status_code=status.HTTP_201_CREATED)
async def login(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceTokenOut:
    """HMAC-authenticated: issue a device-access token + refresh token."""
    try:
        return await DeviceAuthService().login(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device login failed: {e}",
        ) from e


@router.post("/refresh", response_model=DeviceTokenOut)
async def refresh(
    payload: DeviceRefreshRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> DeviceTokenOut:
    """Exchange a device refresh token for a new token pair."""
    try:
        return await DeviceAuthService().refresh(db, payload.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {e}",
        ) from e


@router.post("/heartbeat", response_model=DeviceHeartbeatOut)
async def heartbeat(
    payload: DeviceHeartbeatRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceHeartbeatOut:
    """Record a device heartbeat and return the server time."""
    try:
        return await DeviceAuthService().heartbeat(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Heartbeat failed: {e}",
        ) from e


@router.get("/config", response_model=DeviceConfigDownloadOut)
async def download_config(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceConfigDownloadOut:
    """Download the device's current configuration payload."""
    try:
        return await DeviceAuthService().get_config(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch config: {e}",
        ) from e
