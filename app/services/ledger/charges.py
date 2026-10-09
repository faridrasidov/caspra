# app/services/ledger/charges.py

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
    ConflictError,
    InsufficientFundsError,
    ValidationError,
)
from app.models.ledger.wallet import (
    LedgerAccountType,
    LedgerDirection,
    LedgerEntry,
    Refund,
    RefundStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services.ledger._base import LedgerBase
from app.utils.idempotency import canonical_request_hash
from app.utils.money import assert_integer_amount


class ChargeOperations(LedgerBase):
    """Device charges and refunds of posted transactions."""

    async def refund(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        transaction_id: UUID,
        idempotency_key: UUID,
        amount_minor: int | None,
        reason: str | None,
    ) -> Refund:
        """Reverse a posted transaction via a compensating credit entry."""
        request_hash = canonical_request_hash(
            "transaction.refund",
            transaction_id=transaction_id,
            amount_minor=amount_minor,
            reason=reason,
        )
        existing = await self._replay(db, tenant_id, idempotency_key, request_hash)
        if existing is not None:
            stmt = select(Refund).where(Refund.refund_transaction_id == existing.id)
            prior = (await db.execute(stmt)).scalars().first()
            if prior is not None:
                return prior
            raise ConflictError(
                "Idempotency key belongs to a non-refund transaction",
                code="idempotency_conflict",
            )

        original = await self._get_transaction(db, tenant_id, transaction_id, for_update=True)
        if original.type not in {
            TransactionType.DEBIT.value,
            TransactionType.CAPTURE.value,
        }:
            raise ValidationError("Only debit or capture transactions can be refunded")

        refunded_stmt = select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.tenant_id == tenant_id,
            Refund.original_transaction_id == original.id,
            Refund.status == RefundStatus.COMPLETED.value,
        )
        already_refunded = int((await db.execute(refunded_stmt)).scalar_one())
        remaining = original.amount_minor - already_refunded
        if remaining <= 0 or original.status == TransactionStatus.REVERSED.value:
            raise ValidationError("Transaction has already been fully refunded")

        refund_amount = amount_minor if amount_minor is not None else remaining
        assert_integer_amount(refund_amount)
        if refund_amount > remaining:
            raise ValidationError(
                f"Refund amount exceeds remaining refundable amount ({remaining})"
            )

        if original.wallet_id is None:
            raise ValidationError("Original transaction has no wallet to refund")
        wallet = await self._get_wallet_locked(db, tenant_id, original.wallet_id)

        refund_txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            type=TransactionType.REFUND.value,
            amount_minor=refund_amount,
            currency=original.currency,
            status=TransactionStatus.POSTED.value,
            wallet_id=wallet.id,
            customer_id=original.customer_id,
            description=reason,
        )
        db.add(refund_txn)
        await db.flush()

        wallet_account = await self._wallet_account(db, tenant_id, wallet)
        revenue_account = await self._system_account(
            db, tenant_id, LedgerAccountType.MERCHANT_REVENUE, original.currency
        )
        db.add_all(
            [
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=refund_txn.id,
                    account_id=wallet_account.id,
                    wallet_id=wallet.id,
                    direction=LedgerDirection.CREDIT.value,
                    amount_minor=refund_amount,
                    currency=original.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=refund_txn.id,
                    account_id=revenue_account.id,
                    wallet_id=None,
                    direction=LedgerDirection.DEBIT.value,
                    amount_minor=refund_amount,
                    currency=original.currency,
                ),
            ]
        )
        wallet.balance_minor += refund_amount
        if already_refunded + refund_amount == original.amount_minor:
            original.status = TransactionStatus.REVERSED.value

        refund_row = Refund(
            tenant_id=tenant_id,
            original_transaction_id=original.id,
            refund_transaction_id=refund_txn.id,
            amount_minor=refund_amount,
            currency=original.currency,
            reason=reason,
        )
        db.add(refund_row)
        await self._enqueue_transaction_webhooks(
            db,
            refund_txn,
            event_types=["transaction.posted", "transaction.refunded"],
        )
        try:
            await db.commit()
            await db.refresh(refund_row)
            return refund_row
        except IntegrityError:
            await db.rollback()
            replay = await self._replay(db, tenant_id, idempotency_key, request_hash)
            if replay is None:
                raise
            stmt = select(Refund).where(Refund.refund_transaction_id == replay.id)
            prior = (await db.execute(stmt)).scalars().first()
            if prior is None:
                raise ConflictError(
                    "Idempotency key belongs to a non-refund transaction",
                    code="idempotency_conflict",
                ) from None
            return prior

    async def charge(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet_id: UUID,
        *,
        amount_minor: int,
        currency: str,
        idempotency_key: UUID,
        device_id: UUID | None = None,
        description: str | None = None,
    ) -> Transaction:
        """Debit a wallet at the point of sale. Re-checks balance under the lock.

        Mirrors :meth:`deduct` but stamps the originating ``device_id`` on the
        transaction so the ledger records which reader posted the charge.
        """
        assert_integer_amount(amount_minor)
        request_hash = canonical_request_hash(
            "wallet.charge",
            wallet_id=wallet_id,
            amount_minor=amount_minor,
            currency=currency,
            device_id=device_id,
            description=description,
        )
        existing = await self._replay(db, tenant_id, idempotency_key, request_hash)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, currency)
        available = wallet.balance_minor - await self._active_hold_total(db, tenant_id, wallet_id)
        if available < amount_minor:
            raise InsufficientFundsError

        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            type=TransactionType.DEBIT.value,
            amount_minor=amount_minor,
            currency=wallet.currency,
            status=TransactionStatus.POSTED.value,
            wallet_id=wallet.id,
            customer_id=wallet.customer_id,
            device_id=device_id,
            description=description,
        )
        db.add(txn)
        await db.flush()
        wallet_account = await self._wallet_account(db, tenant_id, wallet)
        revenue_account = await self._system_account(
            db, tenant_id, LedgerAccountType.MERCHANT_REVENUE, wallet.currency
        )
        db.add_all(
            [
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=wallet_account.id,
                    wallet_id=wallet.id,
                    direction=LedgerDirection.DEBIT.value,
                    amount_minor=amount_minor,
                    currency=wallet.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=revenue_account.id,
                    wallet_id=None,
                    direction=LedgerDirection.CREDIT.value,
                    amount_minor=amount_minor,
                    currency=wallet.currency,
                ),
            ]
        )
        wallet.balance_minor -= amount_minor
        return await self._commit_transaction(db, txn, tenant_id, idempotency_key, request_hash)
