# app/services/ledger/wallets.py

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
    InsufficientFundsError,
    ValidationError,
)
from app.models.ledger.wallet import (
    LedgerDirection,
    LedgerEntry,
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
from app.services.ledger._base import LedgerBase
from app.utils.idempotency import canonical_request_hash
from app.utils.money import assert_integer_amount


class WalletOperations(LedgerBase):
    """Top-up, deduct and wallet-to-wallet transfer."""

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
