# app/services/ledger.py

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
    ConflictError,
    InsufficientFundsError,
    NotFoundError,
    ValidationError,
)
from app.models.ledger.hold import Hold, HoldStatus
from app.models.ledger.wallet import (
    LedgerAccount,
    LedgerAccountStatus,
    LedgerAccountType,
    LedgerDirection,
    LedgerEntry,
    Refund,
    RefundStatus,
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
from app.services.webhook import WebhookService
from app.utils.idempotency import canonical_request_hash, find_existing_by_idempotency_key
from app.utils.money import assert_integer_amount

DEFAULT_HOLD_EXPIRES_SECONDS = 15 * 60
MAX_HOLD_EXPIRES_SECONDS = 24 * 60 * 60


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
        request_hash = canonical_request_hash(
            "wallet.topup",
            wallet_id=wallet_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            description=payload.description,
        )
        existing = await self._replay(db, tenant_id, payload.idempotency_key, request_hash)
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
            request_hash=request_hash,
            description=payload.description,
        )
        wallet.balance_minor += payload.amount_minor
        return await self._commit_transaction(
            db, txn, tenant_id, payload.idempotency_key, request_hash
        )

    async def deduct(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet_id: UUID,
        payload: WalletDeductRequest,
    ) -> Transaction:
        """Debit a wallet (money out). Re-checks balance under the row lock."""
        assert_integer_amount(payload.amount_minor)
        request_hash = canonical_request_hash(
            "wallet.deduct",
            wallet_id=wallet_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            description=payload.description,
        )
        existing = await self._replay(db, tenant_id, payload.idempotency_key, request_hash)
        if existing is not None:
            return existing

        wallet = await self._get_wallet_locked(db, tenant_id, wallet_id)
        self._assert_currency(wallet, payload.currency)
        available = wallet.balance_minor - await self._active_hold_total(db, tenant_id, wallet_id)
        if available < payload.amount_minor:
            raise InsufficientFundsError

        txn = await self._post(
            db,
            tenant_id=tenant_id,
            wallet=wallet,
            txn_type=TransactionType.DEBIT,
            direction=LedgerDirection.DEBIT,
            amount_minor=payload.amount_minor,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            description=payload.description,
        )
        wallet.balance_minor -= payload.amount_minor
        return await self._commit_transaction(
            db, txn, tenant_id, payload.idempotency_key, request_hash
        )

    async def transfer(
        self, db: AsyncSession, tenant_id: UUID, payload: WalletTransferRequest
    ) -> Transaction:
        """Move value between two wallets with a balanced double-entry."""
        assert_integer_amount(payload.amount_minor)
        if payload.from_wallet_id == payload.to_wallet_id:
            raise ValidationError("Cannot transfer to the same wallet")

        request_hash = canonical_request_hash(
            "wallet.transfer",
            from_wallet_id=payload.from_wallet_id,
            to_wallet_id=payload.to_wallet_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            description=payload.description,
        )
        existing = await self._replay(db, tenant_id, payload.idempotency_key, request_hash)
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
        held = await self._active_hold_total(db, tenant_id, from_wallet.id)
        if from_wallet.balance_minor - held < payload.amount_minor:
            raise InsufficientFundsError

        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
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

        from_account = await self._wallet_account(db, tenant_id, from_wallet)
        to_account = await self._wallet_account(db, tenant_id, to_wallet)
        db.add_all(
            [
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=from_account.id,
                    wallet_id=from_wallet.id,
                    direction=LedgerDirection.DEBIT.value,
                    amount_minor=payload.amount_minor,
                    currency=payload.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=to_account.id,
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
        return await self._commit_transaction(
            db, txn, tenant_id, payload.idempotency_key, request_hash
        )

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
        request_hash: str,
        description: str | None,
    ) -> Transaction:
        txn = Transaction(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
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
        wallet_account = await self._wallet_account(db, tenant_id, wallet)
        counterparty_type = (
            LedgerAccountType.CASH_CLEARING
            if direction == LedgerDirection.CREDIT
            else LedgerAccountType.MERCHANT_REVENUE
        )
        counterparty = await self._system_account(db, tenant_id, counterparty_type, wallet.currency)
        counterparty_direction = (
            LedgerDirection.DEBIT if direction == LedgerDirection.CREDIT else LedgerDirection.CREDIT
        )
        db.add_all(
            [
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=wallet_account.id,
                    wallet_id=wallet.id,
                    direction=direction.value,
                    amount_minor=amount_minor,
                    currency=wallet.currency,
                ),
                LedgerEntry(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    account_id=counterparty.id,
                    wallet_id=None,
                    direction=counterparty_direction.value,
                    amount_minor=amount_minor,
                    currency=wallet.currency,
                ),
            ]
        )
        return txn

    async def _replay(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        idempotency_key: UUID,
        request_hash: str,
    ) -> Transaction | None:
        return await find_existing_by_idempotency_key(
            db,
            Transaction,
            idempotency_key,
            tenant_id,
            request_hash,
        )

    async def _replay_hold(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        idempotency_key: UUID,
        request_hash: str,
    ) -> Hold | None:
        return await find_existing_by_idempotency_key(
            db,
            Hold,
            idempotency_key,
            tenant_id,
            request_hash,
        )

    async def _active_hold_total(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> int:
        """Sum of funds reserved by active pre-auth holds on a wallet."""
        stmt = select(func.coalesce(func.sum(Hold.amount_minor), 0)).where(
            Hold.tenant_id == tenant_id,
            Hold.wallet_id == wallet_id,
            Hold.status == HoldStatus.PREAUTH.value,
            or_(Hold.expires_at.is_(None), Hold.expires_at > datetime.now(UTC)),
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
        self,
        db: AsyncSession,
        tenant_id: UUID,
        transaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Transaction:
        stmt = select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == tenant_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        txn = result.scalars().first()
        if txn is None:
            raise NotFoundError("Transaction", str(transaction_id))
        return txn

    async def _wallet_account(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        wallet: Wallet,
    ) -> LedgerAccount:
        stmt = select(LedgerAccount).where(
            LedgerAccount.tenant_id == tenant_id,
            LedgerAccount.wallet_id == wallet.id,
        )
        account = (await db.execute(stmt)).scalars().first()
        if account is None:
            account = LedgerAccount(
                tenant_id=tenant_id,
                code=f"wallet:{wallet.id}",
                type=LedgerAccountType.WALLET_LIABILITY.value,
                currency=wallet.currency,
                status=LedgerAccountStatus.ACTIVE.value,
                wallet_id=wallet.id,
            )
            db.add(account)
            await db.flush()
        return account

    async def _system_account(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        account_type: LedgerAccountType,
        currency: str,
    ) -> LedgerAccount:
        code = f"{account_type.value}:{currency}"
        stmt = select(LedgerAccount).where(
            LedgerAccount.tenant_id == tenant_id,
            LedgerAccount.code == code,
            LedgerAccount.currency == currency,
        )
        account = (await db.execute(stmt)).scalars().first()
        if account is None:
            account = LedgerAccount(
                tenant_id=tenant_id,
                code=code,
                type=account_type.value,
                currency=currency,
                status=LedgerAccountStatus.ACTIVE.value,
            )
            db.add(account)
            await db.flush()
        return account

    async def _commit_transaction(
        self,
        db: AsyncSession,
        transaction: Transaction,
        tenant_id: UUID,
        idempotency_key: UUID,
        request_hash: str,
    ) -> Transaction:
        try:
            event_types = ["transaction.posted"]
            if transaction.type == TransactionType.CREDIT.value:
                event_types.append("topup.confirmed")
            await self._enqueue_transaction_webhooks(db, transaction, event_types=event_types)
            await db.commit()
            await db.refresh(transaction)
            return transaction
        except IntegrityError:
            await db.rollback()
            existing = await self._replay(db, tenant_id, idempotency_key, request_hash)
            if existing is None:
                raise
            return existing

    async def _enqueue_transaction_webhooks(
        self,
        db: AsyncSession,
        transaction: Transaction,
        *,
        event_types: list[str],
    ) -> None:
        payload = {
            "transaction_id": str(transaction.id),
            "wallet_id": str(transaction.wallet_id) if transaction.wallet_id else None,
            "customer_id": (str(transaction.customer_id) if transaction.customer_id else None),
            "device_id": str(transaction.device_id) if transaction.device_id else None,
            "type": transaction.type,
            "status": transaction.status,
            "amount_minor": transaction.amount_minor,
            "currency": transaction.currency,
        }
        webhooks = WebhookService()
        for event_type in event_types:
            await webhooks.enqueue(db, transaction.tenant_id, event_type, payload)

    async def _commit_hold(
        self,
        db: AsyncSession,
        hold: Hold,
        tenant_id: UUID,
        idempotency_key: UUID,
        request_hash: str,
    ) -> Hold:
        try:
            await db.commit()
            await db.refresh(hold)
            return hold
        except IntegrityError:
            await db.rollback()
            existing = await self._replay_hold(db, tenant_id, idempotency_key, request_hash)
            if existing is None:
                raise
            return existing

    @staticmethod
    def _assert_currency(wallet: Wallet, currency: str) -> None:
        if wallet.currency != currency:
            raise ValidationError(
                f"Currency mismatch: wallet is {wallet.currency}, request is {currency}"
            )
