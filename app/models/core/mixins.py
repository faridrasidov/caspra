# app/models/core/mixins.py

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column."""

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """Adds created_at / updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Adds a tenant_id FK to organizations for tenant-scoped rows."""

    if TYPE_CHECKING:
        __tablename__: str

    @declared_attr
    def tenant_id(cls) -> Mapped[PyUUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey(
                "organizations.id",
                name=f"fk_{cls.__tablename__}_tenant_id_organizations",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        )
