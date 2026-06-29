# app/api/admin/endpoints/reports.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.report import (
    CustomerActivityOut,
    DailyReportOut,
    DeviceReportOut,
    ReportExportOut,
    TopProductsOut,
)
from app.services.report import ReportService

router = APIRouter(prefix="/reports", tags=["admin-reports"])


@router.get("/daily", response_model=DailyReportOut)
async def daily_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DailyReportOut:
    """Daily transaction volume report."""
    try:
        return await ReportService().daily(db, current_admin.tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build daily report: {e}",
        ) from e


@router.get("/devices", response_model=DeviceReportOut)
async def devices_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceReportOut:
    """Per-device activity report (TODO: needs sales-line attribution)."""
    try:
        return await ReportService().devices(db, current_admin.tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build devices report: {e}",
        ) from e


@router.get("/top-products", response_model=TopProductsOut)
async def top_products_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TopProductsOut:
    """Top products by revenue (TODO: needs order/line-item model)."""
    try:
        return await ReportService().top_products(db, current_admin.tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build top-products report: {e}",
        ) from e


@router.get("/customer-activity", response_model=CustomerActivityOut)
async def customer_activity_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    limit: int = Query(50, ge=1, le=500),
) -> CustomerActivityOut:
    """Customer spend/activity ranking."""
    try:
        return await ReportService().customer_activity(db, current_admin.tenant_id, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build customer-activity report: {e}",
        ) from e


@router.get("/export", response_model=ReportExportOut)
async def export_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    report: str = Query("daily"),
    format: str = Query("json"),
) -> ReportExportOut:
    """Export a named report for the caller's tenant."""
    try:
        return await ReportService().export(db, current_admin.tenant_id, report, format)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {e}",
        ) from e
