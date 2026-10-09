# app/services/device_kiosk.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError, NotFoundError, ValidationError
from app.models.device.device import Device, Kiosk
from app.models.device.kiosk_topup import (
    KioskTopupSession,
    KioskTopupStatus,
    PaymentMethod,
)
from app.models.ledger.wallet import Wallet, WalletStatus, WalletType
from app.schemas.device_kiosk import (
    KioskTopupConfirmRequest,
    KioskTopupRequestIn,
)
from app.schemas.wallet import WalletTopupRequest
from app.services.device_card import DeviceCardService
from app.services.ledger import LedgerService
from app.utils.idempotency import find_existing_by_idempotency_key


class DeviceKioskService:
    """Kiosk-driven top-up sessions and available payment methods."""

    def __init__(self) -> None:
        self._cards = DeviceCardService()
        self._ledger = LedgerService()

    async def request_topup(
        self, db: AsyncSession, device: Device, payload: KioskTopupRequestIn
    ) -> KioskTopupSession:
        tenant_id = device.tenant_id
        existing = await find_existing_by_idempotency_key(
            db, KioskTopupSession, payload.idempotency_key, tenant_id
        )
        if existing is not None:
            return existing

        await self._assert_kiosk(db, tenant_id, payload.kiosk_id)
        customer_id = await self._resolve_customer_id(db, tenant_id, payload)

        session = KioskTopupSession(
            tenant_id=tenant_id,
            kiosk_id=payload.kiosk_id,
            customer_id=customer_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            payment_method=payload.payment_method.value,
            status=KioskTopupStatus.REQUESTED.value,
            idempotency_key=payload.idempotency_key,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def confirm_topup(
        self, db: AsyncSession, device: Device, payload: KioskTopupConfirmRequest
    ) -> KioskTopupSession:
        tenant_id = device.tenant_id
        session = await self._get_session(db, tenant_id, payload.session_id)
        if session.status == KioskTopupStatus.CONFIRMED.value:
            return session
        if session.status != KioskTopupStatus.REQUESTED.value:
            raise ConflictError(f"Top-up session is not confirmable (status: {session.status})")
        if session.customer_id is None:
            raise ValidationError("Top-up session has no customer to credit")

        wallet = await self._resolve_credit_wallet(
            db, tenant_id, session.customer_id, session.currency
        )
        txn = await self._ledger.topup(
            db,
            tenant_id,
            wallet.id,
            WalletTopupRequest(
                amount_minor=session.amount_minor,
                currency=session.currency,
                # Keyed on the session, not the confirm request, so concurrent or
                # retried confirms replay one ledger credit instead of posting twice.
                idempotency_key=session.idempotency_key,
                description=f"Kiosk top-up {session.id}",
            ),
        )
        session.status = KioskTopupStatus.CONFIRMED.value
        session.transaction_id = txn.id
        await db.commit()
        await db.refresh(session)
        return session

    async def cancel_topup(
        self, db: AsyncSession, device: Device, session_id: UUID
    ) -> KioskTopupSession:
        session = await self._get_session(db, device.tenant_id, session_id)
        if session.status == KioskTopupStatus.CANCELLED.value:
            return session
        if session.status != KioskTopupStatus.REQUESTED.value:
            raise ConflictError(f"Top-up session cannot be cancelled (status: {session.status})")
        session.status = KioskTopupStatus.CANCELLED.value
        await db.commit()
        await db.refresh(session)
        return session

    async def list_payment_methods(self, db: AsyncSession, device: Device) -> list[PaymentMethod]:
        stmt = select(PaymentMethod).where(
            PaymentMethod.tenant_id == device.tenant_id,
            PaymentMethod.active.is_(True),
        )
        return list((await db.execute(stmt)).scalars().all())

    async def _resolve_customer_id(
        self, db: AsyncSession, tenant_id: UUID, payload: KioskTopupRequestIn
    ) -> UUID | None:
        if payload.customer_id is not None:
            return payload.customer_id
        if payload.card_uid is not None:
            card = await self._cards.get_card_by_uid(db, tenant_id, payload.card_uid)
            return card.customer_id
        return None

    async def _resolve_credit_wallet(
        self, db: AsyncSession, tenant_id: UUID, customer_id: UUID, currency: str
    ) -> Wallet:
        stmt = select(Wallet).where(
            Wallet.tenant_id == tenant_id,
            Wallet.customer_id == customer_id,
            Wallet.type == WalletType.CREDIT.value,
            Wallet.currency == currency,
        )
        wallet = (await db.execute(stmt)).scalars().first()
        if wallet is None:
            raise NotFoundError("Wallet", f"credit/{currency}")
        if wallet.status != WalletStatus.ACTIVE.value:
            raise ValidationError(f"Wallet is not active (status: {wallet.status})")
        return wallet

    async def _assert_kiosk(self, db: AsyncSession, tenant_id: UUID, kiosk_id: UUID) -> None:
        stmt = select(Kiosk.id).where(Kiosk.id == kiosk_id, Kiosk.tenant_id == tenant_id)
        if (await db.execute(stmt)).first() is None:
            raise NotFoundError("Kiosk", str(kiosk_id))

    async def _get_session(
        self, db: AsyncSession, tenant_id: UUID, session_id: UUID
    ) -> KioskTopupSession:
        stmt = select(KioskTopupSession).where(
            KioskTopupSession.id == session_id, KioskTopupSession.tenant_id == tenant_id
        )
        session = (await db.execute(stmt)).scalars().first()
        if session is None:
            raise NotFoundError("Top-up session", str(session_id))
        return session
