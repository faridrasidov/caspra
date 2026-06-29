# app/models/ledger/wallet.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import VARCHAR, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class WalletType(enum.StrEnum):
    CREDIT = "credit"
    TOKEN = "token"  # noqa: S105
    LOYALTY = "loyalty"


class WalletStatus(enum.StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class TransactionType(enum.StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    TRANSFER = "transfer"
    PREAUTH = "preauth"
    CAPTURE = "capture"
    VOID = "void"


class TransactionStatus(enum.StrEnum):
    PENDING = "pending"
    POSTED = "posted"
    FAILED = "failed"
    REVERSED = "reversed"


class LedgerDirection(enum.StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class RefundStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Customer(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """End-user cardholder, scoped to a tenant."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_customers_tenant_external_id"),
    )

    external_id: Mapped[str | None] = mapped_column(VARCHAR(120), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(VARCHAR(200), nullable=True)
    email: Mapped[str | None] = mapped_column(VARCHAR(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(VARCHAR(40), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=CustomerStatus.ACTIVE.value
    )


class Wallet(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A stored-value wallet. Balance is integer minor units, never float."""

    __tablename__ = "wallets"

    customer_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", name="fk_wallets_customer_id_customers", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    type: Mapped[WalletType] = mapped_column(
        VARCHAR(20), nullable=False, default=WalletType.CREDIT.value
    )
    status: Mapped[WalletStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=WalletStatus.ACTIVE.value
    )


class Transaction(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A logical value movement. Idempotent per tenant via idempotency_key."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_transactions_tenant_idempotency_key"
        ),
    )

    idempotency_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[TransactionType] = mapped_column(VARCHAR(20), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=TransactionStatus.POSTED.value
    )
    wallet_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", name="fk_transactions_wallet_id_wallets", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id", name="fk_transactions_customer_id_customers", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )
    device_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_transactions_device_id_devices", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)


class LedgerEntry(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Append-only double-entry row. Never updated or deleted once posted."""

    __tablename__ = "ledger_entries"

    transaction_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_ledger_entries_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    wallet_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", name="fk_ledger_entries_wallet_id_wallets", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[LedgerDirection] = mapped_column(VARCHAR(10), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)


class Refund(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A refund of a previously posted transaction (via compensating entries)."""

    __tablename__ = "refunds"

    original_transaction_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_refunds_original_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    refund_transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_refunds_refund_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    status: Mapped[RefundStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=RefundStatus.COMPLETED.value
    )


class WalletTransfer(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A value transfer between two wallets in the same tenant."""

    __tablename__ = "wallet_transfers"

    from_wallet_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "wallets.id", name="fk_wallet_transfers_from_wallet_id_wallets", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    to_wallet_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "wallets.id", name="fk_wallet_transfers_to_wallet_id_wallets", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_wallet_transfers_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
