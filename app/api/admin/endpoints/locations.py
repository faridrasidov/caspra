# app/api/admin/endpoints/locations.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.location import (
    LocationCreate,
    LocationOut,
    LocationUpdate,
    PaginatedLocationOut,
)
from app.services.location import LocationService

router = APIRouter(prefix="/locations", tags=["admin-locations"])


@router.get("", response_model=PaginatedLocationOut)
async def list_locations(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedLocationOut:
    """List locations for the caller's tenant."""
    try:
        result = await LocationService().list_locations(db, current_admin.tenant_id, page, limit)
        return PaginatedLocationOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list locations: {e}",
        ) from e


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> LocationOut:
    """Create a location."""
    try:
        return await LocationService().create_location(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create location: {e}",
        ) from e


@router.get("/{location_id}", response_model=LocationOut)
async def get_location(
    location_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> LocationOut:
    """Get a single location."""
    try:
        return await LocationService().get_location(db, current_admin.tenant_id, location_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch location: {e}",
        ) from e


@router.patch("/{location_id}", response_model=LocationOut)
async def update_location(
    location_id: UUID,
    payload: LocationUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> LocationOut:
    """Update a location."""
    try:
        return await LocationService().update_location(
            db, current_admin.tenant_id, location_id, payload
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update location: {e}",
        ) from e


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a location."""
    try:
        await LocationService().delete_location(db, current_admin.tenant_id, location_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete location: {e}",
        ) from e
