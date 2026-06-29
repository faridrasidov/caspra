# app/services/device_payment.py


from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device.device import Device
from app.models.ledger.hold import Hold
from app.models.ledger.wallet import Transaction
from app.schemas.device_payment import (
    DeviceCaptureRequest,
    DeviceChargeRequest,
    DevicePaymentOut,
    DevicePreauthRequest,
    DeviceRefundRequest,
    DeviceVoidRequest,
    HoldOut,
)
from app.services.device_card import DeviceCardService
from app.services.ledger import LedgerService


class DevicePaymentService:
    """Reader-driven money movement; all writes go through ``LedgerService``."""

    def __init__(self) -> None:
        self._cards = DeviceCardService()
        self._ledger = LedgerService()

    async def charge(
        self, db: AsyncSession, device: Device, payload: DeviceChargeRequest
    ) -> DevicePaymentOut:
        tenant_id = device.tenant_id
        card = await self._cards.get_card_by_uid(db, tenant_id, payload.card_uid)
        wallet = await self._cards.resolve_wallet(
            db, tenant_id, card, payload.wallet_type, payload.currency
        )
        txn = await self._ledger.charge(
            db,
            tenant_id,
            wallet.id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
            device_id=device.id,
            description=payload.description,
        )
        balance = await self._ledger.get_balance(db, tenant_id, wallet.id)
        return self._to_payment_out(txn, balance.balance_minor)

    async def refund(
        self, db: AsyncSession, device: Device, payload: DeviceRefundRequest
    ) -> DevicePaymentOut:
        tenant_id = device.tenant_id
        refund = await self._ledger.refund(
            db,
            tenant_id,
            payload.transaction_id,
            payload.idempotency_key,
            payload.amount_minor,
            payload.reason,
        )
        balance_minor = None
        if refund.refund_transaction_id is not None:
            txn = await db.get(Transaction, refund.refund_transaction_id)
            if txn is not None and txn.wallet_id is not None:
                wallet = await self._ledger.get_balance(db, tenant_id, txn.wallet_id)
                balance_minor = wallet.balance_minor
        return DevicePaymentOut(
            transaction_id=refund.refund_transaction_id or refund.id,
            status="posted",
            amount_minor=refund.amount_minor,
            currency=refund.currency,
            balance_minor=balance_minor,
        )

    async def preauth(
        self, db: AsyncSession, device: Device, payload: DevicePreauthRequest
    ) -> HoldOut:
        tenant_id = device.tenant_id
        card = await self._cards.get_card_by_uid(db, tenant_id, payload.card_uid)
        wallet = await self._cards.resolve_wallet(
            db, tenant_id, card, payload.wallet_type, payload.currency
        )
        hold = await self._ledger.preauth(
            db,
            tenant_id,
            wallet.id,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
            card_id=card.id,
            device_id=device.id,
            expires_in_s=payload.expires_in_s,
        )
        return self._to_hold_out(hold)

    async def capture(
        self, db: AsyncSession, device: Device, payload: DeviceCaptureRequest
    ) -> DevicePaymentOut:
        tenant_id = device.tenant_id
        txn = await self._ledger.capture(
            db, tenant_id, payload.hold_id, payload.idempotency_key, payload.amount_minor
        )
        balance_minor = None
        if txn.wallet_id is not None:
            wallet = await self._ledger.get_balance(db, tenant_id, txn.wallet_id)
            balance_minor = wallet.balance_minor
        return self._to_payment_out(txn, balance_minor)

    async def void(self, db: AsyncSession, device: Device, payload: DeviceVoidRequest) -> HoldOut:
        hold = await self._ledger.void(db, device.tenant_id, payload.hold_id)
        return self._to_hold_out(hold)

    @staticmethod
    def _to_payment_out(txn: Transaction, balance_minor: int | None) -> DevicePaymentOut:
        return DevicePaymentOut(
            transaction_id=txn.id,
            status=txn.status,
            amount_minor=txn.amount_minor,
            currency=txn.currency,
            wallet_id=txn.wallet_id,
            balance_minor=balance_minor,
        )

    @staticmethod
    def _to_hold_out(hold: Hold) -> HoldOut:
        return HoldOut(
            hold_id=hold.id,
            status=hold.status,
            amount_minor=hold.amount_minor,
            currency=hold.currency,
            wallet_id=hold.wallet_id,
            expires_at=hold.expires_at,
        )
