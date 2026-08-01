"""offline and delivery workflows

Revision ID: a93f06d2b714
Revises: 8d61c3a7e4b2
Create Date: 2026-07-30 14:30:00+00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a93f06d2b714"
down_revision: str | Sequence[str] | None = "8d61c3a7e4b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE refresh_tokens SET family_id = id")
    op.alter_column(
        "refresh_tokens",
        "family_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_foreign_key(
        "fk_refresh_tokens_replaced_by_id_refresh_tokens",
        "refresh_tokens",
        "refresh_tokens",
        ["replaced_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "offline_policies",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("uid_risk_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_transaction_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_card_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_device_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_outage_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_queue_age_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("max_queue_size", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "max_transaction_minor >= 0 AND max_card_total_minor >= 0 "
            "AND max_device_total_minor >= 0 AND max_outage_total_minor >= 0",
            name="ck_offline_policies_nonnegative_amounts",
        ),
        sa.CheckConstraint(
            "max_queue_age_seconds >= 60 AND max_queue_size >= 1 "
            "AND sync_interval_seconds >= 5",
            name="ck_offline_policies_valid_limits",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organizations.id"],
            name="fk_offline_policies_tenant_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_offline_policies_tenant_id"),
    )
    op.create_index("ix_offline_policies_id", "offline_policies", ["id"])
    op.create_index("ix_offline_policies_tenant_id", "offline_policies", ["tenant_id"])

    op.add_column("webhooks", sa.Column("previous_secret", sa.VARCHAR(255), nullable=True))
    op.add_column(
        "webhooks",
        sa.Column("secret_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "offline_transactions",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "offline_transactions",
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "offline_transactions",
        sa.Column("card_uid", sa.VARCHAR(120), nullable=True),
    )
    op.add_column(
        "offline_transactions",
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "offline_transactions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "offline_transactions",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY tenant_id, device_id
                           ORDER BY created_at, id
                       ) AS sequence_number
                FROM offline_transactions
            )
            UPDATE offline_transactions ot
            SET occurred_at = COALESCE(
                    NULLIF(ot.payload ->> 'occurred_at', '')::timestamptz,
                    ot.created_at
                ),
                sequence_number = ranked.sequence_number,
                card_uid = COALESCE(NULLIF(ot.payload ->> 'card_uid', ''), 'legacy'),
                amount_minor = GREATEST(
                    COALESCE(NULLIF(ot.payload ->> 'amount_minor', '')::bigint, 1),
                    1
                )
            FROM ranked
            WHERE ranked.id = ot.id
            """
        )
    else:
        op.execute(
            """
            UPDATE offline_transactions AS current
            SET occurred_at = current.created_at,
                sequence_number = (
                    SELECT count(*)
                    FROM offline_transactions AS earlier
                    WHERE earlier.tenant_id = current.tenant_id
                      AND earlier.device_id = current.device_id
                      AND (
                          earlier.created_at < current.created_at
                          OR (
                              earlier.created_at = current.created_at
                              AND earlier.id <= current.id
                          )
                      )
                ),
                card_uid = 'legacy',
                amount_minor = 1
            """
        )
    op.alter_column(
        "offline_transactions",
        "occurred_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "offline_transactions",
        "sequence_number",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "offline_transactions",
        "card_uid",
        existing_type=sa.VARCHAR(120),
        nullable=False,
    )
    op.alter_column(
        "offline_transactions",
        "amount_minor",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_offline_transactions_tenant_device_sequence",
        "offline_transactions",
        ["tenant_id", "device_id", "sequence_number"],
    )
    op.create_check_constraint(
        "ck_offline_transactions_positive_values",
        "offline_transactions",
        "sequence_number > 0 AND amount_minor > 0",
    )
    op.create_foreign_key(
        "fk_offline_transactions_reviewed_by_user_id_users",
        "offline_transactions",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "device_commands",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "device_commands",
        sa.Column("last_error", sa.VARCHAR(500), nullable=True),
    )
    op.create_index(
        "ix_device_commands_lease_expires_at",
        "device_commands",
        ["lease_expires_at"],
    )

    op.add_column(
        "webhook_deliveries",
        sa.Column("response_body", sa.VARCHAR(2000), nullable=True),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column("error", sa.VARCHAR(1000), nullable=True),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "webhook_deliveries",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_webhook_deliveries_status",
        "webhook_deliveries",
        ["status"],
    )
    op.create_index(
        "ix_webhook_deliveries_next_retry_at",
        "webhook_deliveries",
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_next_retry_at",
        table_name="webhook_deliveries",
    )
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_column("webhook_deliveries", "locked_at")
    op.drop_column("webhook_deliveries", "delivered_at")
    op.drop_column("webhook_deliveries", "error")
    op.drop_column("webhook_deliveries", "response_body")

    op.drop_index("ix_device_commands_lease_expires_at", table_name="device_commands")
    op.drop_column("device_commands", "last_error")
    op.drop_column("device_commands", "delivery_attempts")
    op.drop_column("device_commands", "acknowledged_at")
    op.drop_column("device_commands", "delivered_at")
    op.drop_column("device_commands", "lease_expires_at")

    op.drop_constraint(
        "fk_offline_transactions_reviewed_by_user_id_users",
        "offline_transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_offline_transactions_positive_values",
        "offline_transactions",
        type_="check",
    )
    op.drop_constraint(
        "uq_offline_transactions_tenant_device_sequence",
        "offline_transactions",
        type_="unique",
    )
    op.drop_column("offline_transactions", "reviewed_by_user_id")
    op.drop_column("offline_transactions", "reviewed_at")
    op.drop_column("offline_transactions", "amount_minor")
    op.drop_column("offline_transactions", "card_uid")
    op.drop_column("offline_transactions", "sequence_number")
    op.drop_column("offline_transactions", "occurred_at")

    op.drop_column("webhooks", "secret_rotated_at")
    op.drop_column("webhooks", "previous_secret")
    op.drop_index("ix_offline_policies_tenant_id", table_name="offline_policies")
    op.drop_index("ix_offline_policies_id", table_name="offline_policies")
    op.drop_table("offline_policies")

    op.drop_constraint(
        "fk_refresh_tokens_replaced_by_id_refresh_tokens",
        "refresh_tokens",
        type_="foreignkey",
    )
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "revoked_at")
    op.drop_column("refresh_tokens", "replaced_by_id")
    op.drop_column("refresh_tokens", "family_id")
