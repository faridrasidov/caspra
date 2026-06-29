# app/api/admin/endpoints/audit.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.audit import AuditLogOut, PaginatedAuditLogOut
from app.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["admin-audit"])


@router.get("", response_model=PaginatedAuditLogOut)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedAuditLogOut:
    """List audit logs for the caller's tenant."""
    try:
        result = await AuditService().list_logs(db, current_admin.tenant_id, page, limit)
        return PaginatedAuditLogOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list audit logs: {e}",
        ) from e


@router.get("/{log_id}", response_model=AuditLogOut)
async def get_audit_log(
    log_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> AuditLogOut:
    """Get a single audit log entry."""
    try:
        return await AuditService().get_log(db, current_admin.tenant_id, log_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audit log: {e}",
        ) from e
