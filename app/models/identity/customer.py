from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerIdentity(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "customer_identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_customer_identity_email"),
        UniqueConstraint("customer_id", name="uq_customer_identity_customer"),
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    email: Mapped[str] = mapped_column(String(320))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    invitation_hash: Mapped[str | None] = mapped_column(String(64))
    invitation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CustomerSession(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "customer_sessions"
    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_identities.id", ondelete="RESTRICT"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentCheckout(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "payment_checkouts"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_checkout_key"),)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[UUID] = mapped_column()
    request_hash: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    bonus_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    provider: Mapped[str] = mapped_column(String(40))
    provider_reference: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="started")
    package_snapshot: Mapped[dict | None] = mapped_column(JSON)
    receipt_id: Mapped[UUID | None] = mapped_column(ForeignKey("receipts.id", ondelete="RESTRICT"))
