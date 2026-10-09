# app/api/admin/endpoints/reports.py

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.report import (
    CustomerActivityOut,
    DailyReportOut,
    ReportExportOut,
)
from app.services.report import ReportService

router = APIRouter(prefix="/reports", tags=["admin-reports"])


@router.get("/daily", response_model=DailyReportOut)
async def daily_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DailyReportOut:
    """Daily transaction volume report."""
    return await ReportService().daily(db, current_admin.tenant_id)


@router.get("/customer-activity", response_model=CustomerActivityOut)
async def customer_activity_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    limit: int = Query(50, ge=1, le=500),
) -> CustomerActivityOut:
    """Customer spend/activity ranking."""
    return await ReportService().customer_activity(db, current_admin.tenant_id, limit)


@router.get("/export", response_model=ReportExportOut)
async def export_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    report: str = Query("daily"),
    format: str = Query("json"),
) -> ReportExportOut:
    """Export a named report for the caller's tenant."""
    return await ReportService().export(db, current_admin.tenant_id, report, format)
