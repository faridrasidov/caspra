from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import require_admin_permission
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.reconciliation import ReconciliationReportOut
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix="/ledger", tags=["admin-ledger"])


@router.get("/reconciliation", response_model=ReconciliationReportOut)
async def reconciliation_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(require_admin_permission(AdminPermission.AUDIT_READ))],
    issue_limit: int = Query(500, ge=1, le=5000),
) -> ReconciliationReportOut:
    return await ReconciliationService().report(
        db,
        current_admin.tenant_id,
        issue_limit=issue_limit,
    )
