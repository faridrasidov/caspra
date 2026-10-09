# tests/device/test_kiosk_topup.py

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.domain_errors import ConflictError, NotFoundError, ValidationError
from app.models.device.device import Device, Kiosk
from app.models.device.kiosk_topup import PaymentMethod, PaymentMethodCode
from app.models.ledger.wallet import Customer, Wallet
from app.schemas.device_kiosk import KioskTopupConfirmRequest, KioskTopupRequestIn
from app.services.device_kiosk import DeviceKioskService

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def kiosk_env(db_session, seeded_device) -> dict:
    tenant_id = UUID(seeded_device["tenant_id"])
    kiosk = Kiosk(tenant_id=tenant_id, name="Lobby kiosk")
    db_session.add(kiosk)
    db_session.add_all(
        [
            PaymentMethod(tenant_id=tenant_id, code=PaymentMethodCode.CASH, label="Cash"),
            PaymentMethod(tenant_id=tenant_id, code=PaymentMethodCode.QR, label="QR", active=False),
        ]
    )
    await db_session.commit()
    device = await db_session.get(Device, UUID(seeded_device["device_id"]))
    return {**seeded_device, "kiosk_id": kiosk.id, "device": device}


def _request(env: dict, **overrides) -> KioskTopupRequestIn:
    data = {
        "kiosk_id": env["kiosk_id"],
        "card_uid": env["card_uid"],
        "amount_minor": 2_500,
        "currency": "USD",
        "payment_method": PaymentMethodCode.CASH,
        "idempotency_key": uuid4(),
    }
    data.update(overrides)
    return KioskTopupRequestIn(**data)


async def _balance(db_session, env: dict) -> int:
    stmt = select(Wallet.balance_minor).where(Wallet.id == UUID(env["wallet_id"]))
    return (await db_session.execute(stmt)).scalar_one()


class TestKioskTopup:
    """Kiosk request → confirm/cancel flow."""

    async def test_confirm_credits_wallet_once(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        session = await service.request_topup(db_session, device, _request(kiosk_env))
        session_id = session.id
        assert str(session.customer_id) == kiosk_env["customer_id"]
        assert await _balance(db_session, kiosk_env) == 10_000

        confirm = KioskTopupConfirmRequest(session_id=session_id, idempotency_key=uuid4())
        confirmed = await service.confirm_topup(db_session, device, confirm)
        txn_id = confirmed.transaction_id
        assert confirmed.status == "confirmed"
        assert txn_id is not None
        assert await _balance(db_session, kiosk_env) == 12_500

        again = KioskTopupConfirmRequest(session_id=session_id, idempotency_key=uuid4())
        replay = await service.confirm_topup(db_session, device, again)
        assert replay.transaction_id == txn_id
        assert await _balance(db_session, kiosk_env) == 12_500

    async def test_request_is_idempotent(self, db_session, kiosk_env):
        service = DeviceKioskService()
        request = _request(kiosk_env)
        first = await service.request_topup(db_session, kiosk_env["device"], request)
        replay = await service.request_topup(db_session, kiosk_env["device"], request)
        assert replay.id == first.id

    async def test_cancelled_session_cannot_be_confirmed(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        session = await service.request_topup(db_session, device, _request(kiosk_env))
        session_id = session.id
        cancelled = await service.cancel_topup(db_session, device, session_id)
        assert cancelled.status == "cancelled"

        confirm = KioskTopupConfirmRequest(session_id=session_id, idempotency_key=uuid4())
        with pytest.raises(ConflictError, match="not confirmable"):
            await service.confirm_topup(db_session, device, confirm)
        assert await _balance(db_session, kiosk_env) == 10_000

    async def test_confirmed_session_cannot_be_cancelled(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        session = await service.request_topup(db_session, device, _request(kiosk_env))
        session_id = session.id
        await service.confirm_topup(
            db_session,
            device,
            KioskTopupConfirmRequest(session_id=session_id, idempotency_key=uuid4()),
        )
        with pytest.raises(ConflictError, match="cannot be cancelled"):
            await service.cancel_topup(db_session, device, session_id)

    async def test_anonymous_session_cannot_be_confirmed(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        session = await service.request_topup(
            db_session, device, _request(kiosk_env, card_uid=None)
        )
        confirm = KioskTopupConfirmRequest(session_id=session.id, idempotency_key=uuid4())
        with pytest.raises(ValidationError, match="no customer"):
            await service.confirm_topup(db_session, device, confirm)

    async def test_missing_wallet_currency_is_not_found(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        session = await service.request_topup(
            db_session, device, _request(kiosk_env, currency="EUR")
        )
        confirm = KioskTopupConfirmRequest(session_id=session.id, idempotency_key=uuid4())
        with pytest.raises(NotFoundError, match="credit/EUR"):
            await service.confirm_topup(db_session, device, confirm)

    async def test_frozen_wallet_is_rejected(self, db_session, kiosk_env):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        wallet = await db_session.get(Wallet, UUID(kiosk_env["wallet_id"]))
        wallet.status = "frozen"
        await db_session.commit()

        session = await service.request_topup(db_session, device, _request(kiosk_env))
        confirm = KioskTopupConfirmRequest(session_id=session.id, idempotency_key=uuid4())
        with pytest.raises(ValidationError, match="not active"):
            await service.confirm_topup(db_session, device, confirm)


class TestKioskAccess:
    """Tenant scoping for kiosks, sessions and payment methods."""

    async def test_unknown_kiosk_is_not_found(self, db_session, kiosk_env):
        with pytest.raises(NotFoundError, match="Kiosk"):
            await DeviceKioskService().request_topup(
                db_session, kiosk_env["device"], _request(kiosk_env, kiosk_id=uuid4())
            )

    async def test_other_tenant_device_cannot_confirm(
        self, db_session, kiosk_env, seeded_device_other
    ):
        service = DeviceKioskService()
        session = await service.request_topup(db_session, kiosk_env["device"], _request(kiosk_env))
        other_device = await db_session.get(Device, UUID(seeded_device_other["device_id"]))
        confirm = KioskTopupConfirmRequest(session_id=session.id, idempotency_key=uuid4())
        with pytest.raises(NotFoundError, match="Top-up session"):
            await service.confirm_topup(db_session, other_device, confirm)

    async def test_other_tenant_customer_is_never_credited(
        self, db_session, kiosk_env, seeded_device_other
    ):
        service = DeviceKioskService()
        device = kiosk_env["device"]
        foreign = await db_session.get(Customer, UUID(seeded_device_other["customer_id"]))
        session = await service.request_topup(
            db_session, device, _request(kiosk_env, card_uid=None, customer_id=foreign.id)
        )
        confirm = KioskTopupConfirmRequest(session_id=session.id, idempotency_key=uuid4())
        with pytest.raises(NotFoundError, match="Wallet"):
            await service.confirm_topup(db_session, device, confirm)

    async def test_only_active_payment_methods_are_listed(self, db_session, kiosk_env):
        methods = await DeviceKioskService().list_payment_methods(db_session, kiosk_env["device"])
        assert [m.code for m in methods] == ["cash"]
