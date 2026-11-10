from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Machine(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint("device_id", name="uq_machine_reader"),
        CheckConstraint("price_minor > 0 AND price_revision > 0", name="ck_machine_price"),
    )
    name: Mapped[str] = mapped_column(String(200))
    location_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT")
    )
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"))
    price_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    price_revision: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default="available")


class PriceRevision(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "price_revisions"
    __table_args__ = (UniqueConstraint("machine_id", "revision", name="uq_machine_price_revision"),)
    machine_id: Mapped[UUID] = mapped_column(ForeignKey("machines.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    price_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))


class PricingSchedule(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "pricing_schedules"
    __table_args__ = (
        CheckConstraint(
            "price_minor > 0 AND weekday >= 0 AND weekday < 7 AND start_minute >= 0 "
            "AND end_minute <= 1440 AND start_minute < end_minute",
            name="ck_pricing_schedule",
        ),
    )
    machine_id: Mapped[UUID] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    weekday: Mapped[int] = mapped_column(Integer)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    price_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlaySession(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "play_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_play_idempotency"),
        UniqueConstraint("transaction_id", name="uq_play_transaction"),
    )
    machine_id: Mapped[UUID] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"), index=True
    )
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"))
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[UUID] = mapped_column()
    request_hash: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    refund_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    price_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="authorized", index=True)
    activation_outcome: Mapped[str | None] = mapped_column(String(20))
    execute_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(String(500))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
