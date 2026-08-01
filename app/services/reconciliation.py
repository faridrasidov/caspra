from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import set_metric_gauge
from app.models.ledger.wallet import (
    LedgerAccount,
    LedgerDirection,
    LedgerEntry,
    Transaction,
    Wallet,
)
from app.schemas.reconciliation import ReconciliationIssue, ReconciliationReportOut


class ReconciliationService:
    """Read-only verification of ledger balance and wallet cache integrity."""

    async def report(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        *,
        issue_limit: int = 500,
    ) -> ReconciliationReportOut:
        issues: list[ReconciliationIssue] = []

        transaction_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.tenant_id == tenant_id)
                )
            ).scalar_one()
        )
        transaction_rows = (
            await db.execute(
                select(
                    Transaction.id,
                    Transaction.currency,
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    LedgerEntry.direction == LedgerDirection.DEBIT.value,
                                    LedgerEntry.amount_minor,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("debits"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    LedgerEntry.direction == LedgerDirection.CREDIT.value,
                                    LedgerEntry.amount_minor,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("credits"),
                )
                .outerjoin(
                    LedgerEntry,
                    (LedgerEntry.transaction_id == Transaction.id)
                    & (LedgerEntry.tenant_id == tenant_id),
                )
                .where(Transaction.tenant_id == tenant_id)
                .group_by(Transaction.id, Transaction.currency)
            )
        ).all()
        for row in transaction_rows:
            debit = int(row.debits)
            credit = int(row.credits)
            if debit != credit:
                issues.append(
                    ReconciliationIssue(
                        kind="unbalanced_transaction",
                        resource_id=row.id,
                        currency=row.currency,
                        expected_minor=debit,
                        actual_minor=credit,
                        difference_minor=credit - debit,
                        detail="Transaction debits and credits differ",
                    )
                )

        wallet_rows = (
            await db.execute(
                select(
                    Wallet.id,
                    Wallet.currency,
                    Wallet.balance_minor,
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    LedgerEntry.direction == LedgerDirection.CREDIT.value,
                                    LedgerEntry.amount_minor,
                                ),
                                else_=-LedgerEntry.amount_minor,
                            )
                        ),
                        0,
                    ).label("ledger_balance"),
                )
                .outerjoin(
                    LedgerEntry,
                    (LedgerEntry.wallet_id == Wallet.id) & (LedgerEntry.tenant_id == tenant_id),
                )
                .where(Wallet.tenant_id == tenant_id)
                .group_by(Wallet.id, Wallet.currency, Wallet.balance_minor)
            )
        ).all()
        for row in wallet_rows:
            expected = int(row.ledger_balance)
            actual = int(row.balance_minor)
            if expected != actual:
                issues.append(
                    ReconciliationIssue(
                        kind="wallet_balance_mismatch",
                        resource_id=row.id,
                        currency=row.currency,
                        expected_minor=expected,
                        actual_minor=actual,
                        difference_minor=actual - expected,
                        detail="Cached wallet balance differs from immutable entries",
                    )
                )

        mismatch_rows = (
            await db.execute(
                select(LedgerEntry.id)
                .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
                .where(
                    LedgerEntry.tenant_id == tenant_id,
                    LedgerAccount.tenant_id != LedgerEntry.tenant_id,
                )
            )
        ).scalars()
        issues.extend(
            [
                ReconciliationIssue(
                    kind="tenant_mismatch",
                    resource_id=entry_id,
                    detail="Ledger entry references an account owned by another tenant",
                )
                for entry_id in mismatch_rows
            ]
        )

        set_metric_gauge(
            "reconciliation_differences",
            len(issues),
            tenant_id=str(tenant_id),
        )
        return ReconciliationReportOut(
            healthy=not issues,
            generated_at=datetime.now(UTC),
            checked_transactions=transaction_count,
            checked_wallets=len(wallet_rows),
            issues=issues[:issue_limit],
        )
