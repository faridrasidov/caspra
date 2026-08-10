from sqlalchemy import func, select, text

from app.models.ledger.wallet import Transaction
from app.services.reconciliation import ReconciliationService
from app.services.report import ReportService
from scripts.seed_mock_data import SeedConfig, seed_mock_data


async def test_seed_mock_data_builds_balanced_thirty_day_dataset(db_session):
    if db_session.bind.dialect.name == "sqlite":
        await db_session.execute(text("PRAGMA foreign_keys = ON"))

    config = SeedConfig(
        tenant_slug="test-demo-30d",
        tenant_name="Test Demo Tenant",
        admin_email="seed-demo@example.test",
        admin_password="test-only-password",
        days=30,
        customers=5,
        transactions_per_day=2,
        random_seed=7,
    )

    result = await seed_mock_data(db_session, config)
    await db_session.flush()

    daily = await ReportService().daily(db_session, result.tenant_id)
    reconciliation = await ReconciliationService().report(db_session, result.tenant_id)
    oldest, newest = (
        await db_session.execute(
            select(func.min(Transaction.created_at), func.max(Transaction.created_at)).where(
                Transaction.tenant_id == result.tenant_id
            )
        )
    ).one()

    assert len(daily.rows) == 30
    assert result.transactions >= config.customers + config.days * config.transactions_per_day
    # SQLite drops timezone metadata from DateTime values, so compare calendar
    # boundaries here; production PostgreSQL retains the UTC offsets.
    assert oldest.date() == result.date_from.date()
    assert newest.date() == result.date_to.date()
    assert reconciliation.healthy is True
    assert reconciliation.checked_transactions == result.transactions
    assert reconciliation.checked_wallets == config.customers
