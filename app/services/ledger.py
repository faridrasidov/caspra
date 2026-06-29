# app/services/ledger.py

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
    ConflictError,
    InsufficientFundsError,
    NotFoundError,
    ValidationError,
)
from app.models.ledger.hold import Hold, HoldStatus
from app.models.ledger.wallet import (
    LedgerDirection,
    LedgerEntry,
    Refund,
    Transaction,
    TransactionStatus,
    TransactionType,
    Wallet,
    WalletTransfer,
)
from app.schemas.wallet import (
    WalletDeductRequest,
    WalletTopupRequest,
    WalletTransferRequest,
)
from app.utils.idempotency import find_existing_by_idempotency_key
from app.utils.money import assert_integer_amount


class LedgerService:
    """Core money movement: top-up, deduct, transfer, refund.

    Enforces integer minor units, idempotency, row-level locking, append-only
    double-entry, and tenant isolation.
    """

    async def topup(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet_id: UUID,
        payload: WalletTopupRequest,
    ) -> Transaction:
        """Credit a wallet (money in). Idempotent and atomic."""
        assert_integer_amount(payload.amount_minor)
        existing = await self._replay(db, tenant_id, payload.idempotency_key)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, payload.currency)

        txn = await self._post(
            db,
            tenant_id=tenant_id,
            wallet=wallet,
            txn_type=TransactionType.CREDIT,
            direction=LedgerDirection.CREDIT,
            amount_minor=payload.amount_minor,
            idempotency_key=payload.idempotency_key,
            description=payload.description,
        )
        wallet.balance_minor += payload.amount_minor
        await db.commit()
        await db.refresh(txn)
        return txn

    async def deduct(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet_id: UUID,
        payload: WalletDeductRequest,
    ) -> Transaction:
        """Debit a wallet (money out). Re-checks balance under the row lock."""
        assert_integer_amount(payload.amount_minor)
        existing = await self._replay(db, tenant_id, payload.idempotency_key)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, payload.currency)
        if wallet.balance_minor < payload.amount_minor:
            raise InsufficientFundsError

        txn = await self._post(
            db,
            tenant_id=tenant_id,
            wallet=wallet,
            txn_type=TransactionType.DEBIT,
            direction=LedgerDirection.DEBIT,
            amount_minor=payload.amount_minor,
            idempotency_key=payload.idempotency_key,
            description=payload.description,
        )
        wallet.balance_minor -= payload.amount_minor
        await db.commit()
        await db.refresh(txn)
        return txn

    async def transfer(
        self, db: AsyncSession, tenant_id: UUID, payload: WalletTransferRequest
    ) -> Transaction:
        """Move value between two wallets with a balanced double-entry."""
        assert_integer_amount(payload.amount_minor)
        if payload.from_wallet_id == payload.to_wallet_id:
            raise ValidationError("Cannot transfer to the same wallet")

        existing = await self._replay(db, tenant_id, payload.idempotency_key)
        if existing is not None:
            return existing

        # Lock wallets in a deterministic order (by id) to avoid deadlocks.
        wallets: dict[UUID, Wallet] = {}
        for wallet_id in sorted([payload.from_wallet_id, payload.to_wallet_id], key=str):
            wallets[wallet_id] = await self._get_wallet_locked(db, tenant_id, wallet_id)
        from_wallet = wallets[payload.from_wallet_id]
        to_wallet = wallets[payload.to_wallet_id]

        self._assert_currency(from_wallet, payload.currency)
        self._assert_currency(to_wallet, payload.currency)
        if from_wallet.balance_minor < payload.amount_minor:
            raise InsufficientFundsError

        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=payload.idempotency_key,
            type=TransactionType.TRANSFER.value,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            status=TransactionStatus.POSTED.value,
            wallet_id=from_wallet.id,
            customer_id=from_wallet.customer_id,
            description=payload.description,
        )
        db.add(txn)
        await db.flush()

        db.add_all(
            [
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    wallet_id=from_wallet.id,
                    direction=LedgerDirection.DEBIT.value,
                    amount_minor=payload.amount_minor,
                    currency=payload.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    wallet_id=to_wallet.id,
                    direction=LedgerDirection.CREDIT.value,
                    amount_minor=payload.amount_minor,
                    currency=payload.currency,
                ),
            ]
        )
        db.add(
            WalletTransfer(
                tenant_id=tenant_id,
                from_wallet_id=from_wallet.id,
                to_wallet_id=to_wallet.id,
                amount_minor=payload.amount_minor,
                currency=payload.currency,
                transaction_id=txn.id,
            )
        )
        from_wallet.balance_minor -= payload.amount_minor
        to_wallet.balance_minor += payload.amount_minor
        await db.commit()
        await db.refresh(txn)
        return txn

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
        original = await self._get_transaction(db, tenant_id, transaction_id)
        if original.type != TransactionType.DEBIT.value:
            raise ValidationError("Only debit transactions can be refunded")
        if original.status == TransactionStatus.REVERSED.value:
            raise ValidationError("Transaction has already been refunded")

        refund_amount = amount_minor if amount_minor is not None else original.amount_minor
        assert_integer_amount(refund_amount)
        if refund_amount > original.amount_minor:
            raise ValidationError("Refund amount exceeds original transaction amount")

        existing = await self._replay(db, tenant_id, idempotency_key)
        if existing is not None:
            stmt = select(Refund).where(Refund.refund_transaction_id == existing.id)
            prior = (await db.execute(stmt)).scalars().first()
            if prior is not None:
                return prior

        if original.wallet_id is None:
            raise ValidationError("Original transaction has no wallet to refund")
        wallet = await self._get_wallet_locked(db, tenant_id, original.wallet_id)

        refund_txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
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

        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                transaction_id=refund_txn.id,
                wallet_id=wallet.id,
                direction=LedgerDirection.CREDIT.value,
                amount_minor=refund_amount,
                currency=original.currency,
            )
        )
        wallet.balance_minor += refund_amount
        if refund_amount == original.amount_minor:
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
        await db.commit()
        await db.refresh(refund_row)
        return refund_row

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
        existing = await self._replay(db, tenant_id, idempotency_key)
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
        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                transaction_id=txn.id,
                wallet_id=wallet.id,
                direction=LedgerDirection.DEBIT.value,
                amount_minor=amount_minor,
                currency=wallet.currency,
            )
        )
        wallet.balance_minor -= amount_minor
        await db.commit()
        await db.refresh(txn)
        return txn

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
        existing = await self._replay_hold(db, tenant_id, idempotency_key)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, currency)
        available = wallet.balance_minor - await self._active_hold_total(db, tenant_id, wallet_id)
        if available < amount_minor:
            raise InsufficientFundsError

        expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in_s)
            if expires_in_s is not None
            else None
        )
        hold = Hold(
            tenant_id=tenant_id,
            wallet_id=wallet.id,
            card_id=card_id,
            device_id=device_id,
            amount_minor=amount_minor,
            currency=wallet.currency,
            status=HoldStatus.PREAUTH.value,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        db.add(hold)
        await db.commit()
        await db.refresh(hold)
        return hold

    async def capture(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        hold_id: UUID,
        idempotency_key: UUID,
        amount_minor: int | None = None,
    ) -> Transaction:
        """Capture a pre-auth hold: post the debit ledger entry and settle funds."""
        existing = await self._replay(db, tenant_id, idempotency_key)
        if existing is not None:
            return existing

        hold = await self._get_hold(db, tenant_id, hold_id)
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
        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                transaction_id=txn.id,
                wallet_id=wallet.id,
                direction=LedgerDirection.DEBIT.value,
                amount_minor=capture_amount,
                currency=wallet.currency,
            )
        )
        wallet.balance_minor -= capture_amount
        hold.status = HoldStatus.CAPTURED.value
        hold.capture_transaction_id = txn.id
        await db.commit()
        await db.refresh(txn)
        return txn

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

    async def get_balance(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> Wallet:
        stmt = select(Wallet).where(Wallet.id == wallet_id, Wallet.tenant_id == tenant_id)
        result = await db.execute(stmt)
        wallet = result.scalars().first()
        if wallet is None:
            raise NotFoundError("Wallet", str(wallet_id))
        return wallet

    # ----- internal helpers -----

    async def _post(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        wallet: Wallet,
        txn_type: TransactionType,
        direction: LedgerDirection,
        amount_minor: int,
        idempotency_key: UUID,
        description: str | None,
    ) -> Transaction:
        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            type=txn_type.value,
            amount_minor=amount_minor,
            currency=wallet.currency,
            status=TransactionStatus.POSTED.value,
            wallet_id=wallet.id,
            customer_id=wallet.customer_id,
            description=description,
        )
        db.add(txn)
        await db.flush()
        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                transaction_id=txn.id,
                wallet_id=wallet.id,
                direction=direction.value,
                amount_minor=amount_minor,
                currency=wallet.currency,
            )
        )
        return txn

    async def _replay(
        self, db: AsyncSession, tenant_id: UUID, idempotency_key: UUID
    ) -> Transaction | None:
        return await find_existing_by_idempotency_key(db, Transaction, idempotency_key, tenant_id)

    async def _replay_hold(
        self, db: AsyncSession, tenant_id: UUID, idempotency_key: UUID
    ) -> Hold | None:
        return await find_existing_by_idempotency_key(db, Hold, idempotency_key, tenant_id)

    async def _active_hold_total(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> int:
        """Sum of funds reserved by active pre-auth holds on a wallet."""
        stmt = select(func.coalesce(func.sum(Hold.amount_minor), 0)).where(
            Hold.tenant_id == tenant_id,
            Hold.wallet_id == wallet_id,
            Hold.status == HoldStatus.PREAUTH.value,
        )
        return int((await db.execute(stmt)).scalar_one())

    async def _get_hold(self, db: AsyncSession, tenant_id: UUID, hold_id: UUID) -> Hold:
        stmt = select(Hold).where(Hold.id == hold_id, Hold.tenant_id == tenant_id).with_for_update()
        hold = (await db.execute(stmt)).scalars().first()
        if hold is None:
            raise NotFoundError("Hold", str(hold_id))
        return hold

    async def _get_wallet_locked(
        self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID
    ) -> Wallet:
        stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id, Wallet.tenant_id == tenant_id)
            .with_for_update()
        )
        result = await db.execute(stmt)
        wallet = result.scalars().first()
        if wallet is None:
            raise NotFoundError("Wallet", str(wallet_id))
        return wallet

    async def _get_transaction(
        self, db: AsyncSession, tenant_id: UUID, transaction_id: UUID
    ) -> Transaction:
        stmt = select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == tenant_id
        )
        result = await db.execute(stmt)
        txn = result.scalars().first()
        if txn is None:
            raise NotFoundError("Transaction", str(transaction_id))
        return txn

    @staticmethod
    def _assert_currency(wallet: Wallet, currency: str) -> None:
        if wallet.currency != currency:
            raise ValidationError(
                f"Currency mismatch: wallet is {wallet.currency}, request is {currency}"
            )
