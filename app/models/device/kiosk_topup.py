# app/models/device/kiosk_topup.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import VARCHAR, BigInteger, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PaymentMethodCode(enum.StrEnum):
    CASH = "cash"
    CARD = "card"
    QR = "qr"


class KioskTopupStatus(enum.StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentMethod(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A tenant-scoped payment method offered at kiosks/POS."""

    __tablename__ = "payment_methods"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_payment_methods_tenant_code"),)

    code: Mapped[PaymentMethodCode] = mapped_column(VARCHAR(20), nullable=False)
    label: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class KioskTopupSession(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A kiosk-initiated top-up session; idempotent and replay-safe."""

    __tablename__ = "kiosk_topup_sessions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_kiosk_topup_sessions_tenant_idempotency_key"
        ),
    )

    kiosk_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", name="fk_kiosk_topup_sessions_kiosk_id_kiosks", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            name="fk_kiosk_topup_sessions_customer_id_customers",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    payment_method: Mapped[PaymentMethodCode] = mapped_column(VARCHAR(20), nullable=False)
    status: Mapped[KioskTopupStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=KioskTopupStatus.REQUESTED.value
    )
    idempotency_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    request_hash: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_kiosk_topup_sessions_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
