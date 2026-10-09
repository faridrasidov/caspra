import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.domain_errors import ValidationError
from app.models.device.device import Device, Kiosk
from app.models.device.kiosk_topup import PaymentMethodCode
from app.models.ledger.wallet import Refund, Transaction, Wallet
from app.schemas.device_kiosk import KioskTopupConfirmRequest, KioskTopupRequestIn
from app.schemas.wallet import WalletTopupRequest
from app.services.device_kiosk import DeviceKioskService
from app.services.ledger import LedgerService

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ["DATABASE_URL"].startswith("sqlite"),
        reason="PostgreSQL row-lock and uniqueness-race coverage",
    ),
]


async def test_concurrent_idempotent_topups_post_once(db_engine, seeded_device):
    tenant_id = UUID(seeded_device["tenant_id"])
    wallet_id = UUID(seeded_device["wallet_id"])
    idempotency_key = uuid4()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def topup_once():
        async with session_factory() as session:
            return await LedgerService().topup(
                session,
                tenant_id,
                wallet_id,
                WalletTopupRequest(
                    amount_minor=500,
                    currency="USD",
                    idempotency_key=idempotency_key,
                ),
            )

    first, second = await asyncio.gather(topup_once(), topup_once())
    assert first.id == second.id

    async with session_factory() as session:
        count = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.idempotency_key == idempotency_key)
                )
            ).scalar_one()
        )
        balance = (
            await session.execute(select(Wallet.balance_minor).where(Wallet.id == wallet_id))
        ).scalar_one()
    assert count == 1
    assert balance == int(seeded_device["balance_minor"]) + 500


async def test_concurrent_refunds_cannot_exceed_original(db_engine, seeded_device):
    tenant_id = UUID(seeded_device["tenant_id"])
    wallet_id = UUID(seeded_device["wallet_id"])
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        original = await LedgerService().charge(
            session,
            tenant_id,
            wallet_id,
            amount_minor=3_000,
            currency="USD",
            idempotency_key=uuid4(),
        )
        original_id = original.id

    async def refund_once():
        async with session_factory() as session:
            return await LedgerService().refund(
                session,
                tenant_id,
                original_id,
                uuid4(),
                2_000,
                "concurrent refund",
            )

    outcomes = await asyncio.gather(
        refund_once(),
        refund_once(),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, ValidationError) for item in outcomes) == 1

    async with session_factory() as session:
        refunded = int(
            (
                await session.execute(
                    select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
                        Refund.original_transaction_id == original_id
                    )
                )
            ).scalar_one()
        )
    assert refunded == 2_000


async def test_concurrent_kiosk_confirms_credit_once(db_engine, seeded_device):
    tenant_id = UUID(seeded_device["tenant_id"])
    wallet_id = UUID(seeded_device["wallet_id"])
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        kiosk = Kiosk(tenant_id=tenant_id, name="Lobby kiosk")
        session.add(kiosk)
        await session.commit()
        device = await session.get(Device, UUID(seeded_device["device_id"]))
        topup = await DeviceKioskService().request_topup(
            session,
            device,
            KioskTopupRequestIn(
                kiosk_id=kiosk.id,
                card_uid=seeded_device["card_uid"],
                amount_minor=1_000,
                currency="USD",
                payment_method=PaymentMethodCode.CASH,
                idempotency_key=uuid4(),
            ),
        )
        topup_id = topup.id

    async def confirm_once():
        async with session_factory() as session:
            device = await session.get(Device, UUID(seeded_device["device_id"]))
            return await DeviceKioskService().confirm_topup(
                session,
                device,
                KioskTopupConfirmRequest(session_id=topup_id, idempotency_key=uuid4()),
            )

    first, second = await asyncio.gather(confirm_once(), confirm_once())
    assert first.transaction_id == second.transaction_id

    async with session_factory() as session:
        balance = (
            await session.execute(select(Wallet.balance_minor).where(Wallet.id == wallet_id))
        ).scalar_one()
    assert balance == int(seeded_device["balance_minor"]) + 1_000
