# app/services/ledger/_base.py

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import (
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
    Transaction,
    TransactionStatus,
    TransactionType,
    Wallet,
)
from app.services.webhook import WebhookService
from app.utils.idempotency import find_existing_by_idempotency_key


class LedgerBase:
    """Shared ledger plumbing: locking, posting, replay and commit helpers."""

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
