from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CashierShift(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "cashier_shifts"
    __table_args__ = (
        CheckConstraint("opening_minor >= 0", name="ck_shift_opening"),
        Index(
            "uq_open_shift_cashier",
            "tenant_id",
            "cashier_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
        Index(
            "uq_open_shift_terminal",
            "tenant_id",
            "terminal",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
    )
    cashier_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    terminal: Mapped[str] = mapped_column(String(120))
    location_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT")
    )
    currency: Mapped[str] = mapped_column(String(3))
    opening_minor: Mapped[int] = mapped_column(BigInteger)
    counted_minor: Mapped[int | None] = mapped_column(BigInteger)
    expected_minor: Mapped[int | None] = mapped_column(BigInteger)
    variance_minor: Mapped[int | None] = mapped_column(BigInteger)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    review_reason: Mapped[str | None] = mapped_column(String(500))


class CashMovement(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "cash_movements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_cash_movement_key"),
    )
    shift_id: Mapped[UUID] = mapped_column(
        ForeignKey("cashier_shifts.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[UUID] = mapped_column()
    request_hash: Mapped[str] = mapped_column(String(64))


class TopupPackage(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "topup_packages"
    __table_args__ = (
        CheckConstraint("paid_minor > 0 AND bonus_minor >= 0", name="ck_package_amounts"),
    )
    name: Mapped[str] = mapped_column(String(200))
    paid_minor: Mapped[int] = mapped_column(BigInteger)
    bonus_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Receipt(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_receipt_key"),
        UniqueConstraint("number", name="uq_receipt_number"),
    )
    number: Mapped[str] = mapped_column(String(80))
    shift_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cashier_shifts.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column()
    request_hash: Mapped[str] = mapped_column(String(64))
    paid_minor: Mapped[int] = mapped_column(BigInteger)
    bonus_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    tender: Mapped[str] = mapped_column(String(20))
    package_snapshot: Mapped[dict | None] = mapped_column(JSON)
    transaction_ids: Mapped[list] = mapped_column(JSON)


class FamilyRelationship(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "family_relationships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "child_id", name="uq_family_child"),
        CheckConstraint("guardian_id <> child_id", name="ck_family_not_self"),
    )
    guardian_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    child_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))


class SpendingLimit(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "spending_limits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", "currency", name="uq_customer_limit"),
        CheckConstraint("daily_minor >= 0", name="ck_daily_limit"),
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    currency: Mapped[str] = mapped_column(String(3))
    daily_minor: Mapped[int] = mapped_column(BigInteger)


class OperationalAlert(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "operational_alerts"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_alert_key"),)
    key: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
