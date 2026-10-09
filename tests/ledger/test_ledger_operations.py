# tests/ledger/test_ledger_operations.py

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.domain_errors import (
    ConflictError,
    InsufficientFundsError,
    NotFoundError,
    ValidationError,
)
from app.models.ledger.wallet import LedgerEntry, Wallet
from app.schemas.wallet import WalletDeductRequest, WalletTopupRequest, WalletTransferRequest
from app.services.ledger import LedgerService

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def two_wallets(db_session, seeded_device) -> dict:
    """The seeded funded wallet plus an empty second wallet for the same customer."""
    tenant_id = UUID(seeded_device["tenant_id"])
    target = Wallet(
        tenant_id=tenant_id,
        customer_id=UUID(seeded_device["customer_id"]),
        balance_minor=0,
        currency="USD",
        type="cash",
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    return {
        "tenant_id": tenant_id,
        "source": UUID(seeded_device["wallet_id"]),
        "target": target.id,
    }


async def _balance(db_session, wallet_id: UUID) -> int:
    stmt = select(Wallet.balance_minor).where(Wallet.id == wallet_id)
    return (await db_session.execute(stmt)).scalar_one()


def _transfer(env: dict, amount_minor: int, **overrides) -> WalletTransferRequest:
    data = {
        "from_wallet_id": env["source"],
        "to_wallet_id": env["target"],
        "amount_minor": amount_minor,
        "currency": "USD",
        "idempotency_key": uuid4(),
    }
    data.update(overrides)
    return WalletTransferRequest(**data)


class TestTransfer:
    """Wallet-to-wallet transfers."""

    async def test_moves_value_with_balanced_entries(self, db_session, two_wallets):
        txn = await LedgerService().transfer(
            db_session, two_wallets["tenant_id"], _transfer(two_wallets, 4_000)
        )

        assert await _balance(db_session, two_wallets["source"]) == 6_000
        assert await _balance(db_session, two_wallets["target"]) == 4_000
        entries = (
            await db_session.execute(
                select(LedgerEntry.direction, func.sum(LedgerEntry.amount_minor))
                .where(LedgerEntry.transaction_id == txn.id)
                .group_by(LedgerEntry.direction)
            )
        ).all()
        assert dict(entries) == {"debit": 4_000, "credit": 4_000}

    async def test_replay_does_not_move_twice(self, db_session, two_wallets):
        service = LedgerService()
        request = _transfer(two_wallets, 1_000)
        first = await service.transfer(db_session, two_wallets["tenant_id"], request)
        replay = await service.transfer(db_session, two_wallets["tenant_id"], request)

        assert replay.id == first.id
        assert await _balance(db_session, two_wallets["target"]) == 1_000

    async def test_insufficient_funds(self, db_session, two_wallets):
        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            await LedgerService().transfer(
                db_session, two_wallets["tenant_id"], _transfer(two_wallets, 10_001)
            )

    async def test_same_wallet_is_rejected(self, db_session, two_wallets):
        request = _transfer(two_wallets, 100, to_wallet_id=two_wallets["source"])
        with pytest.raises(ValidationError, match="same wallet"):
            await LedgerService().transfer(db_session, two_wallets["tenant_id"], request)

    async def test_currency_mismatch_is_rejected(self, db_session, two_wallets):
        with pytest.raises(ValidationError, match="Currency mismatch"):
            await LedgerService().transfer(
                db_session, two_wallets["tenant_id"], _transfer(two_wallets, 100, currency="EUR")
            )

    async def test_other_tenant_wallet_is_not_found(
        self, db_session, two_wallets, seeded_device_other
    ):
        request = _transfer(two_wallets, 100, to_wallet_id=UUID(seeded_device_other["wallet_id"]))
        with pytest.raises(NotFoundError, match="Wallet"):
            await LedgerService().transfer(db_session, two_wallets["tenant_id"], request)

    async def test_cannot_transfer_funds_reserved_by_a_hold(self, db_session, two_wallets):
        service = LedgerService()
        await service.preauth(
            db_session,
            two_wallets["tenant_id"],
            two_wallets["source"],
            amount_minor=8_000,
            currency="USD",
            idempotency_key=uuid4(),
        )

        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            await service.transfer(
                db_session, two_wallets["tenant_id"], _transfer(two_wallets, 5_000)
            )
        assert await _balance(db_session, two_wallets["source"]) == 10_000


class TestHolds:
    """Pre-auth capture and void edge cases."""

    async def _hold(self, db_session, seeded_device, amount_minor: int = 3_000):
        return await LedgerService().preauth(
            db_session,
            UUID(seeded_device["tenant_id"]),
            UUID(seeded_device["wallet_id"]),
            amount_minor=amount_minor,
            currency="USD",
            idempotency_key=uuid4(),
        )

    async def test_partial_capture_releases_remainder(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        hold = await self._hold(db_session, seeded_device)

        txn = await service.capture(db_session, tenant_id, hold.id, uuid4(), 1_200)
        assert txn.amount_minor == 1_200
        assert await _balance(db_session, wallet_id) == 10_000 - 1_200

        # The uncaptured 1_800 is no longer reserved.
        await service.deduct(
            db_session,
            tenant_id,
            wallet_id,
            WalletDeductRequest(amount_minor=8_800, currency="USD", idempotency_key=uuid4()),
        )
        assert await _balance(db_session, wallet_id) == 0

    async def test_capture_more_than_held_is_rejected(self, db_session, seeded_device):
        hold = await self._hold(db_session, seeded_device)
        with pytest.raises(ValidationError, match="exceeds the held amount"):
            await LedgerService().capture(
                db_session, UUID(seeded_device["tenant_id"]), hold.id, uuid4(), 3_001
            )

    async def test_capture_replay_returns_same_transaction(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        hold = await self._hold(db_session, seeded_device)
        key = uuid4()

        first = await service.capture(db_session, tenant_id, hold.id, key)
        replay = await service.capture(db_session, tenant_id, hold.id, key)
        assert replay.id == first.id
        assert await _balance(db_session, UUID(seeded_device["wallet_id"])) == 7_000

    async def test_second_capture_with_new_key_is_rejected(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        hold = await self._hold(db_session, seeded_device)
        hold_id = hold.id
        await service.capture(db_session, tenant_id, hold_id, uuid4())

        with pytest.raises(ConflictError, match="not capturable"):
            await service.capture(db_session, tenant_id, hold_id, uuid4())

    async def test_void_is_idempotent_and_blocks_capture(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        hold = await self._hold(db_session, seeded_device)
        hold_id = hold.id

        assert (await service.void(db_session, tenant_id, hold_id)).status == "voided"
        assert (await service.void(db_session, tenant_id, hold_id)).status == "voided"
        with pytest.raises(ConflictError, match="not capturable"):
            await service.capture(db_session, tenant_id, hold_id, uuid4())

    async def test_captured_hold_cannot_be_voided(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        hold = await self._hold(db_session, seeded_device)
        hold_id = hold.id
        await service.capture(db_session, tenant_id, hold_id, uuid4())

        with pytest.raises(ConflictError, match="cannot be voided"):
            await service.void(db_session, tenant_id, hold_id)

    async def test_other_tenant_cannot_capture(
        self, db_session, seeded_device, seeded_device_other
    ):
        hold = await self._hold(db_session, seeded_device)
        with pytest.raises(NotFoundError, match="Hold"):
            await LedgerService().capture(
                db_session, UUID(seeded_device_other["tenant_id"]), hold.id, uuid4()
            )


class TestRefund:
    """Refund rules beyond the partial-refund cap covered in test_idempotency."""

    async def test_full_refund_restores_balance_and_reverses(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        charge = await service.charge(
            db_session,
            tenant_id,
            wallet_id,
            amount_minor=2_500,
            currency="USD",
            idempotency_key=uuid4(),
        )
        charge_id = charge.id

        refund = await service.refund(db_session, tenant_id, charge_id, uuid4(), None, "Faulty")
        assert refund.amount_minor == 2_500
        assert await _balance(db_session, wallet_id) == 10_000

        with pytest.raises(ValidationError, match="already been fully refunded"):
            await service.refund(db_session, tenant_id, charge_id, uuid4(), None, "Again")

    async def test_topup_cannot_be_refunded(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        topup = await service.topup(
            db_session,
            tenant_id,
            UUID(seeded_device["wallet_id"]),
            WalletTopupRequest(amount_minor=500, currency="USD", idempotency_key=uuid4()),
        )
        with pytest.raises(ValidationError, match="Only debit or capture"):
            await service.refund(db_session, tenant_id, topup.id, uuid4(), None, None)

    async def test_other_tenant_cannot_refund(self, db_session, seeded_device, seeded_device_other):
        charge = await LedgerService().charge(
            db_session,
            UUID(seeded_device["tenant_id"]),
            UUID(seeded_device["wallet_id"]),
            amount_minor=500,
            currency="USD",
            idempotency_key=uuid4(),
        )
        with pytest.raises(NotFoundError, match="Transaction"):
            await LedgerService().refund(
                db_session, UUID(seeded_device_other["tenant_id"]), charge.id, uuid4(), None, None
            )
