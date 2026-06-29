# app/api/public/endpoints/reports.py

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    BalancesReportOut,
    DeviceUsageOut,
    DeviceUsageRow,
    SalesReportOut,
    SalesReportRow,
    TopCustomerRow,
    TopCustomersOut,
    TopProductRow,
    TopProductsReportOut,
)
from app.services.report import ReportService

router = APIRouter(
    prefix="/reports",
    tags=["public-reports"],
    dependencies=[Depends(rate_limit_public)],
)


def _anonymize(value: str) -> str:
    """Return a stable, non-reversible reference for an identifier."""
    return "cust_" + hashlib.sha256(value.encode()).hexdigest()[:16]


@router.get("/sales", response_model=SalesReportOut)
async def sales_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> SalesReportOut:
    """Daily sales volume (credit/debit) for the API key's tenant."""
    try:
        daily = await ReportService().daily(db, ctx.tenant_id)
        rows = [
            SalesReportRow(
                day=row.day.isoformat(),
                transaction_count=row.transaction_count,
                total_credit_minor=row.total_credit_minor,
                total_debit_minor=row.total_debit_minor,
            )
            for row in daily.rows
        ]
        return SalesReportOut(currency=daily.currency, rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build sales report: {e}",
        ) from e


@router.get("/top-customers", response_model=TopCustomersOut)
async def top_customers_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> TopCustomersOut:
    """Top customers by spend, anonymized."""
    try:
        activity = await ReportService().customer_activity(db, ctx.tenant_id)
        rows = [
            TopCustomerRow(
                customer_ref=_anonymize(row.customer_id),
                transaction_count=row.transaction_count,
                total_spent_minor=row.total_spent_minor,
            )
            for row in activity.rows
        ]
        return TopCustomersOut(rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build top-customers report: {e}",
        ) from e


@router.get("/top-products", response_model=TopProductsReportOut)
async def top_products_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> TopProductsReportOut:
    """Top products by revenue.

    TODO: requires an order/sales-line model not yet in scope; returns empty.
    """
    try:
        report = await ReportService().top_products(db, ctx.tenant_id)
        rows = [
            TopProductRow(
                product_id=row.product_id,
                product_name=row.product_name,
                units_sold=row.units_sold,
                revenue_minor=row.revenue_minor,
            )
            for row in report.rows
        ]
        return TopProductsReportOut(rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build top-products report: {e}",
        ) from e


@router.get("/device-usage", response_model=DeviceUsageOut)
async def device_usage_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> DeviceUsageOut:
    """Per-device usage breakdown.

    TODO: requires sales-line attribution not yet in scope; returns empty.
    """
    try:
        report = await ReportService().devices(db, ctx.tenant_id)
        rows = [
            DeviceUsageRow(
                device_id=row.device_id,
                device_name=row.device_name,
                transaction_count=row.transaction_count,
                total_amount_minor=row.total_amount_minor,
            )
            for row in report.rows
        ]
        return DeviceUsageOut(rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build device-usage report: {e}",
        ) from e


@router.get("/balances", response_model=BalancesReportOut)
async def balances_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> BalancesReportOut:
    """Total stored value in circulation, grouped by currency."""
    try:
        return await ReportService().balances_in_circulation(db, ctx.tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build balances report: {e}",
        ) from e
