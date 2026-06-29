# app/services/report.py

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger.wallet import Transaction, TransactionType, Wallet
from app.schemas.public import BalancesReportOut, BalancesReportRow
from app.schemas.report import (
    CustomerActivityOut,
    CustomerActivityRow,
    DailyReportOut,
    DailyReportRow,
    DeviceReportOut,
    ReportExportOut,
    TopProductsOut,
)


class ReportService:
    """Read-only aggregation reports scoped to a tenant.

    NOTE: device/top-product reporting depends on a sales-line model that is not
    yet present; those methods return empty result sets as documented TODOs.
    """

    async def daily(self, db: AsyncSession, tenant_id: UUID) -> DailyReportOut:
        """Aggregate transaction volume grouped by calendar day."""
        day = func.date(Transaction.created_at)
        stmt = (
            select(
                day.label("day"),
                func.count().label("cnt"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type.in_(
                                    [
                                        TransactionType.CREDIT.value,
                                        TransactionType.REFUND.value,
                                    ]
                                ),
                                Transaction.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("credit"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type == TransactionType.DEBIT.value,
                                Transaction.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("debit"),
            )
            .where(Transaction.tenant_id == tenant_id)
            .group_by(day)
            .order_by(day)
        )
        result = await db.execute(stmt)
        rows = [
            DailyReportRow(
                day=row.day,
                transaction_count=row.cnt,
                total_credit_minor=int(row.credit),
                total_debit_minor=int(row.debit),
            )
            for row in result.all()
        ]
        return DailyReportOut(rows=rows)

    async def devices(self, db: AsyncSession, tenant_id: UUID) -> DeviceReportOut:
        """TODO: per-device sales breakdown (needs sales-line attribution)."""
        _ = db, tenant_id
        return DeviceReportOut(rows=[])

    async def top_products(self, db: AsyncSession, tenant_id: UUID) -> TopProductsOut:
        """TODO: top products by revenue (needs order/line-item model)."""
        _ = db, tenant_id
        return TopProductsOut(rows=[])

    async def customer_activity(
        self, db: AsyncSession, tenant_id: UUID, limit: int = 50
    ) -> CustomerActivityOut:
        """Rank customers by transaction count and spend."""
        stmt = (
            select(
                Transaction.customer_id,
                func.count().label("cnt"),
                func.coalesce(func.sum(Transaction.amount_minor), 0).label("spent"),
            )
            .where(
                Transaction.tenant_id == tenant_id,
                Transaction.customer_id.is_not(None),
                Transaction.type == TransactionType.DEBIT.value,
            )
            .group_by(Transaction.customer_id)
            .order_by(func.sum(Transaction.amount_minor).desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = [
            CustomerActivityRow(
                customer_id=str(row.customer_id),
                transaction_count=row.cnt,
                total_spent_minor=int(row.spent),
            )
            for row in result.all()
        ]
        return CustomerActivityOut(rows=rows)

    async def balances_in_circulation(self, db: AsyncSession, tenant_id: UUID) -> BalancesReportOut:
        """Total stored value currently held in wallets, grouped by currency."""
        stmt = (
            select(
                Wallet.currency,
                func.coalesce(func.sum(Wallet.balance_minor), 0).label("total"),
                func.count().label("cnt"),
            )
            .where(Wallet.tenant_id == tenant_id)
            .group_by(Wallet.currency)
            .order_by(Wallet.currency)
        )
        result = await db.execute(stmt)
        rows = [
            BalancesReportRow(
                currency=row.currency,
                total_balance_minor=int(row.total),
                wallet_count=int(row.cnt),
            )
            for row in result.all()
        ]
        return BalancesReportOut(rows=rows)

    async def export(
        self, db: AsyncSession, tenant_id: UUID, report: str = "daily", fmt: str = "json"
    ) -> ReportExportOut:
        """Export a named report. Currently supports the daily report."""
        if report == "daily":
            daily = await self.daily(db, tenant_id)
            rows = [row.model_dump(mode="json") for row in daily.rows]
        else:
            rows = []
        return ReportExportOut(format=fmt, report=report, rows=rows)
