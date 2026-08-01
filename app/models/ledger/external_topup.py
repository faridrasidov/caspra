# app/models/ledger/external_topup.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import VARCHAR, BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExternalTopupStatus(enum.StrEnum):
    STARTED = "started"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExternalTopupSession(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A third-party / mobile-initiated top-up session.

    Distinct from :class:`KioskTopupSession` on purpose: kiosk sessions are
    bound to an on-site ``kiosk_id`` (NOT NULL) and an in-person
    ``payment_method`` (cash/card/qr). External flows have no kiosk, are driven
    by a partner/mobile app, and settle against an ``external_payment_ref``
    returned by a payment gateway. Overloading the kiosk model would require a
    bogus kiosk_id and misuse the payment_method enum, so we keep a separate
    table. Idempotent and replay-safe per tenant.
    """

    __tablename__ = "external_topup_sessions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_external_topup_sessions_tenant_idempotency_key",
        ),
        CheckConstraint(
            "amount_minor > 0",
            name="ck_external_topup_sessions_positive_amount",
        ),
    )

    customer_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            name="fk_external_topup_sessions_customer_id_customers",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    card_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "cards.id",
            name="fk_external_topup_sessions_card_id_cards",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    wallet_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "wallets.id",
            name="fk_external_topup_sessions_wallet_id_wallets",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    status: Mapped[ExternalTopupStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=ExternalTopupStatus.STARTED.value
    )
    idempotency_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    request_hash: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    external_payment_ref: Mapped[str | None] = mapped_column(
        VARCHAR(200), nullable=True, index=True
    )
    transaction_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transactions.id",
            name="fk_external_topup_sessions_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
