# app/models/tenant/webhook_delivery.py

from datetime import datetime
import enum
from uuid import UUID as PyUUID

from sqlalchemy import JSON, VARCHAR, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class WebhookDeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"
    DEAD = "dead"


class WebhookDelivery(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A single dispatch attempt record for an outbound webhook event.

    Recorded synchronously when an event fires; the actual HTTP delivery is
    performed out of band (TODO: async worker/queue). Append a new row per
    logical delivery and update its ``status``/``attempts`` as retries occur.
    """

    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "webhooks.id",
            name="fk_webhook_deliveries_webhook_id_webhooks",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default=WebhookDeliveryStatus.PENDING.value, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(VARCHAR(2000), nullable=True)
    error: Mapped[str | None] = mapped_column(VARCHAR(1000), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
