from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.domain_errors import ConflictError, InsufficientFundsError, ValidationError
from app.models.ledger.wallet import TransactionStatus
from app.schemas.wallet import WalletDeductRequest, WalletTopupRequest
from app.services.ledger import LedgerService

pytestmark = pytest.mark.asyncio


class TestLedgerSafety:
    async def test_same_key_same_request_replays_but_changed_request_conflicts(
        self, db_session, seeded_device
    ):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        idempotency_key = uuid4()
        request = WalletTopupRequest(
            amount_minor=500,
            currency="USD",
            idempotency_key=idempotency_key,
        )

        first = await service.topup(db_session, tenant_id, wallet_id, request)
        replay = await service.topup(db_session, tenant_id, wallet_id, request)
        assert replay.id == first.id

        with pytest.raises(ConflictError, match="different request"):
            await service.topup(
                db_session,
                tenant_id,
                wallet_id,
                request.model_copy(update={"amount_minor": 600}),
            )

    async def test_active_hold_blocks_ordinary_deduction(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        await service.preauth(
            db_session,
            tenant_id,
            wallet_id,
            amount_minor=9_000,
            currency="USD",
            idempotency_key=uuid4(),
        )

        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            await service.deduct(
                db_session,
                tenant_id,
                wallet_id,
                WalletDeductRequest(
                    amount_minor=2_000,
                    currency="USD",
                    idempotency_key=uuid4(),
                ),
            )

    async def test_expired_hold_cannot_be_captured(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        hold = await service.preauth(
            db_session,
            tenant_id,
            wallet_id,
            amount_minor=1_000,
            currency="USD",
            idempotency_key=uuid4(),
            expires_in_s=30,
        )
        hold.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()

        with pytest.raises(ConflictError, match="expired"):
            await service.capture(db_session, tenant_id, hold.id, uuid4())

    async def test_partial_refunds_cannot_exceed_original(self, db_session, seeded_device):
        service = LedgerService()
        tenant_id = UUID(seeded_device["tenant_id"])
        wallet_id = UUID(seeded_device["wallet_id"])
        debit = await service.charge(
            db_session,
            tenant_id,
            wallet_id,
            amount_minor=3_000,
            currency="USD",
            idempotency_key=uuid4(),
        )

        await service.refund(db_session, tenant_id, debit.id, uuid4(), 2_000, "partial")
        with pytest.raises(ValidationError, match="remaining refundable"):
            await service.refund(db_session, tenant_id, debit.id, uuid4(), 2_000, "too much")

        await service.refund(db_session, tenant_id, debit.id, uuid4(), None, "rest")
        await db_session.refresh(debit)
        assert debit.status == TransactionStatus.REVERSED.value
