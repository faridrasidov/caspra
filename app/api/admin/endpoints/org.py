# app/api/admin/endpoints/org.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.organization import (
    OrganizationOut,
    OrganizationUpdate,
    OrgSettingsOut,
    OrgSettingsUpdate,
)
from app.schemas.user import PaginatedUserOut, UserCreate, UserOut, UserUpdate
from app.services.organization import OrganizationService

router = APIRouter(prefix="/org", tags=["admin-org"])


@router.get("", response_model=OrganizationOut)
async def get_organization(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrganizationOut:
    """Get the caller's organization."""
    return await OrganizationService().get_organization(db, current_admin.tenant_id)


@router.patch("", response_model=OrganizationOut)
async def update_organization(
    payload: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrganizationOut:
    """Update the caller's organization."""
    return await OrganizationService().update_organization(db, current_admin.tenant_id, payload)


@router.get("/settings", response_model=OrgSettingsOut)
async def get_org_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrgSettingsOut:
    """Get the organization's general settings."""
    return await OrganizationService().get_settings(db, current_admin.tenant_id)


@router.patch("/settings", response_model=OrgSettingsOut)
async def update_org_settings(
    payload: OrgSettingsUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrgSettingsOut:
    """Update the organization's general settings."""
    return await OrganizationService().update_settings(db, current_admin.tenant_id, payload)


@router.get("/users", response_model=PaginatedUserOut)
async def list_users(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedUserOut:
    """List users in the caller's organization."""
    result = await OrganizationService().list_users(db, current_admin.tenant_id, page, limit)
    return PaginatedUserOut(**result)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> UserOut:
    """Create a user in the caller's organization."""
    return await OrganizationService().create_user(db, current_admin.tenant_id, payload)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> UserOut:
    """Get a single user in the caller's organization."""
    return await OrganizationService().get_user(db, current_admin.tenant_id, user_id)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> UserOut:
    """Update a user in the caller's organization."""
    return await OrganizationService().update_user(db, current_admin.tenant_id, user_id, payload)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a user in the caller's organization."""
    await OrganizationService().delete_user(db, current_admin.tenant_id, user_id)
