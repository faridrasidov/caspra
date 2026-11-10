from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TransactionAllocation(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "transaction_allocations"
    __table_args__ = (
        UniqueConstraint("transaction_id", "wallet_id", name="uq_transaction_allocation_wallet"),
        CheckConstraint("amount_minor > 0", name="ck_allocation_positive"),
    )
    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), index=True
    )
    wallet_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    wallet_type: Mapped[str] = mapped_column(String(20))


class FinancialControl(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "financial_controls"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_financial_controls_tenant"),)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(500))


class ReconciliationRun(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_runs"
    healthy: Mapped[bool] = mapped_column(Boolean)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    report: Mapped[dict] = mapped_column(JSON)
