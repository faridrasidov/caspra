# app/models/audit/audit_log.py

from uuid import UUID as PyUUID

from sqlalchemy import JSON, VARCHAR, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Append-only audit trail of admin actions, scoped to a tenant."""

    __tablename__ = "audit_logs"

    actor_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_audit_logs_actor_user_id_users", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(VARCHAR(80), nullable=True)
    target_id: Mapped[str | None] = mapped_column(VARCHAR(80), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
