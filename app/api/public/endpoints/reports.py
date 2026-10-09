# app/api/public/endpoints/reports.py

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    BalancesReportOut,
    SalesReportOut,
    SalesReportRow,
    TopCustomerRow,
    TopCustomersOut,
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


@router.get("/top-customers", response_model=TopCustomersOut)
async def top_customers_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> TopCustomersOut:
    """Top customers by spend, anonymized."""
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


@router.get("/balances", response_model=BalancesReportOut)
async def balances_report(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.REPORTS_READ))],
) -> BalancesReportOut:
    """Total stored value in circulation, grouped by currency."""
    return await ReportService().balances_in_circulation(db, ctx.tenant_id)
