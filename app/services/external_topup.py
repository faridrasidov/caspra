# app/services/external_topup.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError, NotFoundError
from app.models.ledger.external_topup import ExternalTopupSession, ExternalTopupStatus
from app.models.ledger.wallet import Wallet
from app.schemas.public import ExternalTopupConfirmRequest, ExternalTopupStartRequest
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService
from app.utils.idempotency import canonical_request_hash, find_existing_by_idempotency_key


class ExternalTopupService:
    """Third-party / mobile top-up sessions backed by the ledger.

    Sessions are idempotent and replay-safe per tenant. Confirmation routes the
    actual money movement through :class:`LedgerService` so all ledger
    invariants (row lock, double-entry, idempotency) still hold.
    """

    async def start(
        self, db: AsyncSession, tenant_id: UUID, payload: ExternalTopupStartRequest
    ) -> ExternalTopupSession:
        request_hash = canonical_request_hash(
            "external_topup.start",
            wallet_id=payload.wallet_id,
            customer_id=payload.customer_id,
            card_id=payload.card_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            external_payment_ref=payload.external_payment_ref,
        )
        existing = await find_existing_by_idempotency_key(
            db,
            ExternalTopupSession,
            payload.idempotency_key,
            tenant_id,
            request_hash,
        )
        if existing is not None:
            return existing

        wallet = await self._get_wallet(db, tenant_id, payload.wallet_id)
        if wallet.currency != payload.currency:
            raise ConflictError(
                f"Currency mismatch: wallet is {wallet.currency}, request is {payload.currency}"
            )

        session = ExternalTopupSession(
            tenant_id=tenant_id,
            wallet_id=wallet.id,
            customer_id=payload.customer_id or wallet.customer_id,
            card_id=payload.card_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            status=ExternalTopupStatus.STARTED.value,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            external_payment_ref=payload.external_payment_ref,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def confirm(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        session_id: UUID,
        payload: ExternalTopupConfirmRequest,
    ) -> ExternalTopupSession:
        """Settle a started session by crediting the wallet via the ledger."""
        session = await self._get_session(db, tenant_id, session_id)
        if session.status == ExternalTopupStatus.CONFIRMED.value:
            return session
        if session.status != ExternalTopupStatus.STARTED.value:
            raise ConflictError(f"Top-up session cannot be confirmed (status: {session.status})")
        if session.wallet_id is None:
            raise ConflictError("Top-up session has no wallet to credit")

        if payload.external_payment_ref is not None:
            session.external_payment_ref = payload.external_payment_ref

        # Reuse the session's idempotency_key for the ledger top-up so replays
        # of confirm never double-credit the wallet.
        txn = await LedgerService().topup(
            db,
            tenant_id,
            session.wallet_id,
            WalletTopupRequest(
                amount_minor=session.amount_minor,
                currency=session.currency,
                idempotency_key=session.idempotency_key,
                description=f"External top-up {session.id}",
            ),
        )
        session.status = ExternalTopupStatus.CONFIRMED.value
        session.transaction_id = txn.id
        await db.commit()
        await db.refresh(session)
        return session

    async def cancel(
        self, db: AsyncSession, tenant_id: UUID, session_id: UUID
    ) -> ExternalTopupSession:
        session = await self._get_session(db, tenant_id, session_id)
        if session.status == ExternalTopupStatus.CANCELLED.value:
            return session
        if session.status != ExternalTopupStatus.STARTED.value:
            raise ConflictError(f"Top-up session cannot be cancelled (status: {session.status})")
        session.status = ExternalTopupStatus.CANCELLED.value
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session(
        self, db: AsyncSession, tenant_id: UUID, session_id: UUID
    ) -> ExternalTopupSession:
        return await self._get_session(db, tenant_id, session_id)

    async def _get_session(
        self, db: AsyncSession, tenant_id: UUID, session_id: UUID
    ) -> ExternalTopupSession:
        stmt = select(ExternalTopupSession).where(
            ExternalTopupSession.id == session_id,
            ExternalTopupSession.tenant_id == tenant_id,
        )
        session = (await db.execute(stmt)).scalars().first()
        if session is None:
            raise NotFoundError("Top-up session", str(session_id))
        return session

    async def _get_wallet(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> Wallet:
        stmt = select(Wallet).where(Wallet.id == wallet_id, Wallet.tenant_id == tenant_id)
        wallet = (await db.execute(stmt)).scalars().first()
        if wallet is None:
            raise NotFoundError("Wallet", str(wallet_id))
        return wallet
