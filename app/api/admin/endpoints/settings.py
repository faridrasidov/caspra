# app/api/admin/endpoints/settings.py

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.organization import OrgSettingsOut, OrgSettingsUpdate
from app.schemas.settings import (
    BillingSettingsOut,
    BillingSettingsUpdate,
    SecuritySettingsOut,
    SecuritySettingsUpdate,
)
from app.services.organization import OrganizationService
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["admin-settings"])


@router.get("", response_model=OrgSettingsOut)
async def get_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrgSettingsOut:
    """Get the tenant's general settings."""
    return await OrganizationService().get_settings(db, current_admin.tenant_id)


@router.put("", response_model=OrgSettingsOut)
async def update_settings(
    payload: OrgSettingsUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> OrgSettingsOut:
    """Update the tenant's general settings."""
    return await OrganizationService().update_settings(db, current_admin.tenant_id, payload)


@router.get("/billing", response_model=BillingSettingsOut)
async def get_billing_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> BillingSettingsOut:
    """Get the tenant's billing settings."""
    return await SettingsService().get_billing(db, current_admin.tenant_id)


@router.put("/billing", response_model=BillingSettingsOut)
async def update_billing_settings(
    payload: BillingSettingsUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> BillingSettingsOut:
    """Update the tenant's billing settings."""
    return await SettingsService().update_billing(db, current_admin.tenant_id, payload)


@router.get("/security", response_model=SecuritySettingsOut)
async def get_security_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> SecuritySettingsOut:
    """Get the tenant's security settings."""
    return await SettingsService().get_security(db, current_admin.tenant_id)


@router.put("/security", response_model=SecuritySettingsOut)
async def update_security_settings(
    payload: SecuritySettingsUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> SecuritySettingsOut:
    """Update the tenant's security settings."""
    return await SettingsService().update_security(db, current_admin.tenant_id, payload)
