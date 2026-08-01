"""pilot financial integrity

Revision ID: 8d61c3a7e4b2
Revises: 22b899e90ca7
Create Date: 2026-07-30 12:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8d61c3a7e4b2"
down_revision: str | Sequence[str] | None = "22b899e90ca7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("hmac_secret_encrypted", sa.VARCHAR(512), nullable=True))
    op.add_column(
        "devices",
        sa.Column("hmac_previous_secret_encrypted", sa.VARCHAR(512), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("hmac_secret_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "devices",
        sa.Column("hmac_secret_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )

    for table_name in (
        "transactions",
        "holds",
        "offline_transactions",
        "external_topup_sessions",
        "kiosk_topup_sessions",
    ):
        op.add_column(table_name, sa.Column("request_hash", sa.VARCHAR(64), nullable=True))

    op.create_table(
        "ledger_accounts",
        sa.Column("code", sa.VARCHAR(160), nullable=False),
        sa.Column("type", sa.VARCHAR(40), nullable=False),
        sa.Column("currency", sa.VARCHAR(3), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="active"),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_ledger_accounts_currency_format",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organizations.id"],
            name="fk_ledger_accounts_tenant_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_ledger_accounts_wallet_id_wallets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id", name="uq_ledger_accounts_wallet_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "code",
            "currency",
            name="uq_ledger_accounts_tenant_code_currency",
        ),
    )
    op.create_index("ix_ledger_accounts_id", "ledger_accounts", ["id"])
    op.create_index("ix_ledger_accounts_tenant_id", "ledger_accounts", ["tenant_id"])
    op.create_index("ix_ledger_accounts_wallet_id", "ledger_accounts", ["wallet_id"])

    op.add_column(
        "ledger_entries",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_foreign_key(
        "fk_ledger_entries_account_id_ledger_accounts",
        "ledger_entries",
        "ledger_accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_ledger_entries_transaction_id_transactions",
        "ledger_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_ledger_entries_transaction_id_transactions",
        "ledger_entries",
        "transactions",
        ["transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_ledger_entries_wallet_id_wallets",
        "ledger_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_ledger_entries_wallet_id_wallets",
        "ledger_entries",
        "wallets",
        ["wallet_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("ledger_entries", "wallet_id", existing_type=postgresql.UUID(), nullable=True)

    if op.get_bind().dialect.name == "postgresql":
        _backfill_postgresql()
        op.alter_column(
            "ledger_entries",
            "account_id",
            existing_type=postgresql.UUID(),
            nullable=False,
        )

    _add_financial_constraints()

    if op.get_bind().dialect.name == "postgresql":
        _install_ledger_triggers()


def _backfill_postgresql() -> None:
    op.execute(
        """
        INSERT INTO ledger_accounts
            (id, tenant_id, code, type, currency, status, wallet_id, created_at, updated_at)
        SELECT gen_random_uuid(), w.tenant_id, 'wallet:' || w.id::text,
               'wallet_liability', w.currency, 'active', w.id, now(), now()
        FROM wallets w
        ON CONFLICT (wallet_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ledger_accounts
            (id, tenant_id, code, type, currency, status, created_at, updated_at)
        SELECT gen_random_uuid(), c.tenant_id,
               account_type || ':' || c.currency,
               account_type, c.currency, 'active', now(), now()
        FROM (
            SELECT DISTINCT tenant_id, currency FROM transactions
            UNION
            SELECT DISTINCT tenant_id, currency FROM wallets
        ) c
        CROSS JOIN (
            VALUES ('cash_clearing'), ('merchant_revenue'), ('adjustment')
        ) AS account_types(account_type)
        ON CONFLICT (tenant_id, code, currency) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE ledger_entries le
        SET account_id = la.id
        FROM ledger_accounts la
        WHERE la.wallet_id = le.wallet_id
          AND la.tenant_id = le.tenant_id
        """
    )
    op.execute(
        """
        WITH totals AS (
            SELECT t.id AS transaction_id, t.tenant_id, t.type, t.currency,
                   COALESCE(SUM(CASE WHEN le.direction = 'debit'
                                     THEN le.amount_minor ELSE 0 END), 0) AS debits,
                   COALESCE(SUM(CASE WHEN le.direction = 'credit'
                                     THEN le.amount_minor ELSE 0 END), 0) AS credits
            FROM transactions t
            LEFT JOIN ledger_entries le ON le.transaction_id = t.id
            GROUP BY t.id, t.tenant_id, t.type, t.currency
        )
        INSERT INTO ledger_entries
            (id, tenant_id, transaction_id, account_id, wallet_id,
             direction, amount_minor, currency, created_at, updated_at)
        SELECT gen_random_uuid(), totals.tenant_id, totals.transaction_id, account.id, NULL,
               CASE WHEN totals.credits > totals.debits THEN 'debit' ELSE 'credit' END,
               ABS(totals.credits - totals.debits), totals.currency, now(), now()
        FROM totals
        JOIN ledger_accounts account
          ON account.tenant_id = totals.tenant_id
         AND account.currency = totals.currency
         AND account.type = CASE
             WHEN totals.type = 'credit' THEN 'cash_clearing'
             WHEN totals.type IN ('debit', 'capture', 'refund') THEN 'merchant_revenue'
             ELSE 'adjustment'
         END
        WHERE totals.debits <> totals.credits
        """
    )
    op.execute(
        """
        WITH wallet_totals AS (
            SELECT w.id AS wallet_id, w.tenant_id, w.customer_id, w.currency,
                   w.balance_minor,
                   COALESCE(SUM(CASE
                       WHEN le.direction = 'credit' THEN le.amount_minor
                       WHEN le.direction = 'debit' THEN -le.amount_minor
                       ELSE 0
                   END), 0) AS entry_balance
            FROM wallets w
            LEFT JOIN ledger_entries le ON le.wallet_id = w.id
            GROUP BY w.id, w.tenant_id, w.customer_id, w.currency, w.balance_minor
        ),
        opening_transactions AS (
            INSERT INTO transactions
                (id, tenant_id, idempotency_key, request_hash, type, amount_minor,
                 currency, status, wallet_id, customer_id, description,
                 created_at, updated_at)
            SELECT gen_random_uuid(), wt.tenant_id, gen_random_uuid(), NULL,
                   'adjustment', ABS(wt.balance_minor - wt.entry_balance),
                   wt.currency, 'posted', wt.wallet_id, wt.customer_id,
                   'Migration opening balance', now(), now()
            FROM wallet_totals wt
            WHERE wt.balance_minor <> wt.entry_balance
            RETURNING id, tenant_id, wallet_id, amount_minor, currency
        )
        INSERT INTO ledger_entries
            (id, tenant_id, transaction_id, account_id, wallet_id,
             direction, amount_minor, currency, created_at, updated_at)
        SELECT gen_random_uuid(), tx.tenant_id, tx.id, account.id, tx.wallet_id,
               'credit', tx.amount_minor, tx.currency, now(), now()
        FROM opening_transactions tx
        JOIN ledger_accounts account ON account.wallet_id = tx.wallet_id
        UNION ALL
        SELECT gen_random_uuid(), tx.tenant_id, tx.id, account.id, NULL,
               'debit', tx.amount_minor, tx.currency, now(), now()
        FROM opening_transactions tx
        JOIN ledger_accounts account
          ON account.tenant_id = tx.tenant_id
         AND account.currency = tx.currency
         AND account.type = 'adjustment'
        """
    )


def _add_financial_constraints() -> None:
    op.create_check_constraint(
        "ck_wallets_non_negative_balance",
        "wallets",
        "balance_minor >= 0",
    )
    op.create_check_constraint(
        "ck_wallets_currency_format",
        "wallets",
        "length(currency) = 3 AND currency = upper(currency)",
    )
    op.create_check_constraint(
        "ck_transactions_positive_amount",
        "transactions",
        "amount_minor > 0",
    )
    op.create_check_constraint(
        "ck_transactions_currency_format",
        "transactions",
        "length(currency) = 3 AND currency = upper(currency)",
    )
    op.create_check_constraint(
        "ck_ledger_entries_positive_amount",
        "ledger_entries",
        "amount_minor > 0",
    )
    op.create_check_constraint(
        "ck_ledger_entries_currency_format",
        "ledger_entries",
        "length(currency) = 3 AND currency = upper(currency)",
    )
    op.create_check_constraint("ck_refunds_positive_amount", "refunds", "amount_minor > 0")
    op.create_check_constraint(
        "ck_wallet_transfers_positive_amount",
        "wallet_transfers",
        "amount_minor > 0",
    )
    op.create_check_constraint("ck_holds_positive_amount", "holds", "amount_minor > 0")
    op.create_check_constraint(
        "ck_external_topup_sessions_positive_amount",
        "external_topup_sessions",
        "amount_minor > 0",
    )


def _install_ledger_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION caspra_prevent_ledger_entry_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'posted ledger entries are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ledger_entries_immutable
        BEFORE UPDATE OR DELETE ON ledger_entries
        FOR EACH ROW EXECUTE FUNCTION caspra_prevent_ledger_entry_mutation()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION caspra_assert_balanced_transaction()
        RETURNS trigger AS $$
        DECLARE
            target_transaction uuid;
            debit_total bigint;
            credit_total bigint;
        BEGIN
            target_transaction := COALESCE(NEW.transaction_id, OLD.transaction_id);
            SELECT
                COALESCE(SUM(CASE WHEN direction = 'debit' THEN amount_minor ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount_minor ELSE 0 END), 0)
            INTO debit_total, credit_total
            FROM ledger_entries
            WHERE transaction_id = target_transaction;
            IF debit_total <> credit_total THEN
                RAISE EXCEPTION 'ledger transaction % is not balanced', target_transaction;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_ledger_entries_balanced
        AFTER INSERT ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION caspra_assert_balanced_transaction()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_entries_balanced ON ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS caspra_assert_balanced_transaction()")
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_entries_immutable ON ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS caspra_prevent_ledger_entry_mutation()")

    for constraint, table_name in (
        ("ck_external_topup_sessions_positive_amount", "external_topup_sessions"),
        ("ck_holds_positive_amount", "holds"),
        ("ck_wallet_transfers_positive_amount", "wallet_transfers"),
        ("ck_refunds_positive_amount", "refunds"),
        ("ck_ledger_entries_currency_format", "ledger_entries"),
        ("ck_ledger_entries_positive_amount", "ledger_entries"),
        ("ck_transactions_currency_format", "transactions"),
        ("ck_transactions_positive_amount", "transactions"),
        ("ck_wallets_currency_format", "wallets"),
        ("ck_wallets_non_negative_balance", "wallets"),
    ):
        op.drop_constraint(constraint, table_name, type_="check")

    op.execute(
        """
        DELETE FROM ledger_entries
        WHERE transaction_id IN (
            SELECT id FROM transactions
            WHERE type = 'adjustment' AND description = 'Opening balance migration'
        )
        """
    )
    op.execute(
        """
        DELETE FROM transactions
        WHERE type = 'adjustment' AND description = 'Opening balance migration'
        """
    )
    op.execute("DELETE FROM ledger_entries WHERE wallet_id IS NULL")
    op.drop_constraint(
        "fk_ledger_entries_transaction_id_transactions",
        "ledger_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_ledger_entries_transaction_id_transactions",
        "ledger_entries",
        "transactions",
        ["transaction_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_ledger_entries_wallet_id_wallets",
        "ledger_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_ledger_entries_wallet_id_wallets",
        "ledger_entries",
        "wallets",
        ["wallet_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_ledger_entries_account_id_ledger_accounts",
        "ledger_entries",
        type_="foreignkey",
    )
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_column("ledger_entries", "account_id")
    op.alter_column("ledger_entries", "wallet_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_index("ix_ledger_accounts_wallet_id", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_tenant_id", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_id", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")

    for table_name in (
        "kiosk_topup_sessions",
        "external_topup_sessions",
        "offline_transactions",
        "holds",
        "transactions",
    ):
        op.drop_column(table_name, "request_hash")

    op.drop_column("devices", "hmac_secret_rotated_at")
    op.drop_column("devices", "hmac_secret_version")
    op.drop_column("devices", "hmac_previous_secret_encrypted")
    op.drop_column("devices", "hmac_secret_encrypted")
