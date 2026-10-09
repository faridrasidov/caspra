# app/services/ledger/holds.py

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
    ConflictError,
    InsufficientFundsError,
    ValidationError,
)
from app.models.ledger.hold import Hold, HoldStatus
from app.models.ledger.wallet import (
    LedgerAccountType,
    LedgerDirection,
    LedgerEntry,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services.ledger._base import LedgerBase
from app.utils.idempotency import canonical_request_hash
from app.utils.money import assert_integer_amount

DEFAULT_HOLD_EXPIRES_SECONDS = 15 * 60
MAX_HOLD_EXPIRES_SECONDS = 24 * 60 * 60


class HoldOperations(LedgerBase):
    """Pre-authorisation holds: reserve, capture and void."""

    async def preauth(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet_id: UUID,
        *,
        amount_minor: int,
        currency: str,
        idempotency_key: UUID,
        card_id: UUID | None = None,
        device_id: UUID | None = None,
        expires_in_s: int | None = None,
    ) -> Hold:
        """Reserve funds on a wallet without moving money (no ledger entry yet)."""
        assert_integer_amount(amount_minor)
        expiry_seconds = DEFAULT_HOLD_EXPIRES_SECONDS if expires_in_s is None else expires_in_s
        if not 30 <= expiry_seconds <= MAX_HOLD_EXPIRES_SECONDS:
            raise ValidationError("Hold expiry must be between 30 seconds and 24 hours")
        request_hash = canonical_request_hash(
            "wallet.preauth",
            wallet_id=wallet_id,
            amount_minor=amount_minor,
            currency=currency,
            card_id=card_id,
            device_id=device_id,
            expires_in_s=expiry_seconds,
        )
        existing = await self._replay_hold(db, tenant_id, idempotency_key, request_hash)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, currency)
        available = wallet.balance_minor - await self._active_hold_total(db, tenant_id, wallet_id)
        if available < amount_minor:
            raise InsufficientFundsError

        expires_at = datetime.now(UTC) + timedelta(seconds=expiry_seconds)
        hold = Hold(
            tenant_id=tenant_id,
            wallet_id=wallet.id,
            card_id=card_id,
            device_id=device_id,
            amount_minor=amount_minor,
            currency=wallet.currency,
            status=HoldStatus.PREAUTH.value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            expires_at=expires_at,
        )
        db.add(hold)
        return await self._commit_hold(db, hold, tenant_id, idempotency_key, request_hash)

    async def capture(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        hold_id: UUID,
        idempotency_key: UUID,
        amount_minor: int | None = None,
    ) -> Transaction:
        """Capture a pre-auth hold: post the debit ledger entry and settle funds."""
        request_hash = canonical_request_hash(
            "hold.capture",
            hold_id=hold_id,
            amount_minor=amount_minor,
        )
        existing = await self._replay(db, tenant_id, idempotency_key, request_hash)
        if existing is not None:
            return existing

        hold = await self._get_hold(db, tenant_id, hold_id)
        if hold.expires_at is not None:
            expires_at = hold.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                hold.status = HoldStatus.EXPIRED.value
                await db.commit()
                raise ConflictError("Hold has expired")
        if hold.status != HoldStatus.PREAUTH.value:
            raise ConflictError(f"Hold is not capturable (status: {hold.status})")

        capture_amount = amount_minor if amount_minor is not None else hold.amount_minor
        assert_integer_amount(capture_amount)
        if capture_amount > hold.amount_minor:
            raise ValidationError("Capture amount exceeds the held amount")

        wallet = await self._get_wallet_locked(db, tenant_id, hold.wallet_id)
        if wallet.balance_minor < capture_amount:
            raise InsufficientFundsError

        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            type=TransactionType.CAPTURE.value,
            amount_minor=capture_amount,
            currency=wallet.currency,
            status=TransactionStatus.POSTED.value,
            wallet_id=wallet.id,
            customer_id=wallet.customer_id,
            device_id=hold.device_id,
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
                    amount_minor=capture_amount,
                    currency=wallet.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=revenue_account.id,
                    wallet_id=None,
                    direction=LedgerDirection.CREDIT.value,
                    amount_minor=capture_amount,
                    currency=wallet.currency,
                ),
            ]
        )
        wallet.balance_minor -= capture_amount
        hold.status = HoldStatus.CAPTURED.value
        hold.capture_transaction_id = txn.id
        return await self._commit_transaction(db, txn, tenant_id, idempotency_key, request_hash)

    async def void(self, db: AsyncSession, tenant_id: UUID, hold_id: UUID) -> Hold:
        """Cancel a pre-auth hold and release the reserved funds."""
        hold = await self._get_hold(db, tenant_id, hold_id)
        if hold.status == HoldStatus.VOIDED.value:
            return hold
        if hold.status != HoldStatus.PREAUTH.value:
            raise ConflictError(f"Hold cannot be voided (status: {hold.status})")
        hold.status = HoldStatus.VOIDED.value
        await db.commit()
        await db.refresh(hold)
        return hold
