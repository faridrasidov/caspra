# app/models/tenant/organization.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import JSON, VARCHAR, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OrgStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class LocationStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MembershipStatus(enum.StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    REVOKED = "revoked"


class NotificationLevel(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant root entity. Has no tenant_id (it *is* the tenant)."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    slug: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, unique=True, index=True)
    status: Mapped[OrgStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=OrgStatus.ACTIVE.value
    )
    default_currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False, default="USD")


class OrgSettings(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-tenant general settings."""

    __tablename__ = "org_settings"

    timezone: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="UTC")
    branding: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Membership(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Links a user to an organization with a role (cross-domain via FK columns)."""

    __tablename__ = "memberships"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_memberships_user_id_users", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", name="fk_memberships_role_id_roles", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=MembershipStatus.ACTIVE.value
    )


class Location(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A physical venue/site within a tenant."""

    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    address: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    timezone: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="UTC")
    status: Mapped[LocationStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=LocationStatus.ACTIVE.value
    )


class BillingSettings(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-tenant SaaS billing configuration."""

    __tablename__ = "billing_settings"

    plan: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, default="free")
    billing_email: Mapped[str | None] = mapped_column(VARCHAR(320), nullable=True)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False, default="USD")
    payment_method: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SecuritySettings(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-tenant security policy configuration."""

    __tablename__ = "security_settings"

    mfa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    password_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_allowlist: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Webhook(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Outbound webhook subscription for tenant events."""

    __tablename__ = "webhooks"

    url: Mapped[str] = mapped_column(VARCHAR(1000), nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    secret: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Notification(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Admin-facing notification with a read flag."""

    __tablename__ = "notifications"

    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    message: Mapped[str] = mapped_column(VARCHAR(2000), nullable=False)
    level: Mapped[NotificationLevel] = mapped_column(
        VARCHAR(20), nullable=False, default=NotificationLevel.INFO.value
    )
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_notifications_user_id_users", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
