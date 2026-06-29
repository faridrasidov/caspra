# app/models/ledger/hold.py

from datetime import datetime
import enum
from uuid import UUID as PyUUID

from sqlalchemy import (
    JSON,
    VARCHAR,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class HoldStatus(enum.StrEnum):
    PREAUTH = "preauth"
    CAPTURED = "captured"
    VOIDED = "voided"
    EXPIRED = "expired"


class OfflineTransactionStatus(enum.StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"


class Hold(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A pre-authorization hold reserving funds on a wallet (no ledger movement yet)."""

    __tablename__ = "holds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_holds_tenant_idempotency_key"),
    )

    wallet_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", name="fk_holds_wallet_id_wallets", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", name="fk_holds_card_id_cards", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    device_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", name="fk_holds_device_id_devices", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    status: Mapped[HoldStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=HoldStatus.PREAUTH.value
    )
    idempotency_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_holds_capture_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )


class TempCardAssignment(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """An anonymous temporary card→session assignment (e.g. day passes)."""

    __tablename__ = "temp_card_assignments"

    card_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", name="fk_temp_card_assignments_card_id_cards", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_ref: Mapped[str | None] = mapped_column(VARCHAR(120), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OfflineTransaction(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A queued offline operation uploaded by a device; applied replay-safely."""

    __tablename__ = "offline_transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_offline_transactions_tenant_idempotency_key"
        ),
    )

    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "devices.id", name="fk_offline_transactions_device_id_devices", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[OfflineTransactionStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=OfflineTransactionStatus.PENDING.value
    )
    applied_transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_offline_transactions_applied_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
