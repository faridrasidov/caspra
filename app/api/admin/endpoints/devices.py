# app/api/admin/endpoints/devices.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin, require_admin_permission
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.device import (
    DeviceConfigOut,
    DeviceConfigUpdate,
    DeviceCreate,
    DeviceCredentialOut,
    DeviceOut,
    DeviceProvisioningOut,
    DeviceResetRequest,
    DeviceStatusUpdate,
    DeviceUpdate,
    PaginatedDeviceEventOut,
    PaginatedDeviceOut,
)
from app.schemas.device_ops import DeviceCommandOut
from app.services.device import DeviceService

router = APIRouter(prefix="/devices", tags=["admin-devices"])


@router.get("", response_model=PaginatedDeviceOut)
async def list_devices(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceOut:
    """List devices for the caller's tenant."""
    try:
        result = await DeviceService().list_devices(db, current_admin.tenant_id, page, limit)
        return PaginatedDeviceOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("", response_model=DeviceProvisioningOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceProvisioningOut:
    """Register a new device."""
    try:
        device, raw_secret = await DeviceService().register_device(
            db, current_admin.tenant_id, payload
        )
        return DeviceProvisioningOut(
            **DeviceOut.model_validate(device).model_dump(),
            hmac_secret=raw_secret,
            hmac_secret_version=device.hmac_secret_version,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{device_id}/credentials/rotate", response_model=DeviceCredentialOut)
async def rotate_device_credentials(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceCredentialOut:
    device, raw_secret = await DeviceService().rotate_credentials(
        db, current_admin.tenant_id, device_id
    )
    return DeviceCredentialOut(
        device_id=device.id,
        hmac_secret=raw_secret,
        hmac_secret_version=device.hmac_secret_version,
    )


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Get a single device."""
    try:
        return await DeviceService().get_device(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceOut:
    """Update a device."""
    try:
        return await DeviceService().update_device(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> None:
    """Delete a device."""
    try:
        await DeviceService().delete_device(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{device_id}/status", response_model=DeviceOut)
async def set_device_status(
    device_id: UUID,
    payload: DeviceStatusUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceOut:
    """Set a device's status."""
    try:
        return await DeviceService().set_status(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{device_id}/reset", response_model=DeviceCommandOut)
async def reset_device(
    device_id: UUID,
    payload: DeviceResetRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceCommandOut:
    """Queue a reset command that remains pending until device acknowledgement."""
    try:
        return await DeviceService().reset(
            db,
            current_admin.tenant_id,
            device_id,
            reason=payload.reason,
            requested_by=current_admin.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{device_id}/config", response_model=DeviceConfigOut)
async def get_device_config(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceConfigOut:
    """Get a device's configuration."""
    try:
        return await DeviceService().get_config(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.put("/{device_id}/config", response_model=DeviceConfigOut)
async def update_device_config(
    device_id: UUID,
    payload: DeviceConfigUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> DeviceConfigOut:
    """Update a device's configuration."""
    try:
        return await DeviceService().update_config(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{device_id}/events", response_model=PaginatedDeviceEventOut)
async def list_device_events(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceEventOut:
    """List events emitted by a device."""
    try:
        result = await DeviceService().list_events(
            db, current_admin.tenant_id, device_id, page, limit
        )
        return PaginatedDeviceEventOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
