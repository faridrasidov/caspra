import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.models.ledger.operations import TransactionAllocation
from app.models.ledger.wallet import LedgerEntry
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ["DATABASE_URL"].startswith("sqlite"),
        reason="Migrated PostgreSQL trigger coverage",
    ),
]


class TestMigratedLedgerConstraints:
    async def transaction(self, db, device):
        return await LedgerService().topup(
            db,
            UUID(device["tenant_id"]),
            UUID(device["wallet_id"]),
            WalletTopupRequest(amount_minor=100, currency="USD", idempotency_key=uuid4()),
        )

    async def test_posted_entries_cannot_be_changed(self, db_session, seeded_device):
        txn = await self.transaction(db_session, seeded_device)
        with pytest.raises(DBAPIError, match="immutable"):
            await db_session.execute(
                update(LedgerEntry)
                .where(LedgerEntry.transaction_id == txn.id)
                .values(amount_minor=101)
            )
        await db_session.rollback()

    async def test_unbalanced_posting_is_rejected_at_commit(self, db_session, seeded_device):
        txn = await self.transaction(db_session, seeded_device)
        source = (
            await db_session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.transaction_id == txn.id, LedgerEntry.wallet_id.is_(None)
                )
            )
        ).scalar_one()
        db_session.add(
            LedgerEntry(
                tenant_id=txn.tenant_id,
                transaction_id=txn.id,
                account_id=source.account_id,
                wallet_id=None,
                direction="debit",
                amount_minor=1,
                currency="USD",
            )
        )
        with pytest.raises(DBAPIError, match="not balanced"):
            await db_session.commit()
        await db_session.rollback()

    async def test_entry_currency_must_match_transaction_and_account(
        self, db_session, seeded_device
    ):
        txn = await self.transaction(db_session, seeded_device)
        source = (
            await db_session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.transaction_id == txn.id, LedgerEntry.wallet_id.is_(None)
                )
            )
        ).scalar_one()
        db_session.add(
            LedgerEntry(
                tenant_id=txn.tenant_id,
                transaction_id=txn.id,
                account_id=source.account_id,
                wallet_id=None,
                direction="debit",
                amount_minor=1,
                currency="EUR",
            )
        )
        with pytest.raises(DBAPIError, match="ownership or currency mismatch"):
            await db_session.flush()
        await db_session.rollback()

    async def test_funding_allocations_are_immutable(self, db_session, seeded_device):
        txn = await self.transaction(db_session, seeded_device)
        with pytest.raises(DBAPIError, match="immutable"):
            await db_session.execute(
                update(TransactionAllocation)
                .where(TransactionAllocation.transaction_id == txn.id)
                .values(amount_minor=101)
            )
        await db_session.rollback()
