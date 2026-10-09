# app/api/public/endpoints/org.py

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import OrgStatsOut, PublicOrgOut
from app.services.organization import OrganizationService

router = APIRouter(
    prefix="/org",
    tags=["public-org"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("", response_model=PublicOrgOut)
async def get_org(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.ORG_READ))],
) -> PublicOrgOut:
    """Return public-safe info about the API key's organization."""
    return await OrganizationService().get_organization(db, ctx.tenant_id)


@router.get("/stats", response_model=OrgStatsOut)
async def get_org_stats(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.ORG_READ))],
) -> OrgStatsOut:
    """Return tenant resource counts (customers/cards/devices/transactions)."""
    return await OrganizationService().get_stats(db, ctx.tenant_id)
