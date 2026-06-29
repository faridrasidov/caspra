# app/models/identity/user.py

from datetime import datetime
import enum
from uuid import UUID as PyUUID

from sqlalchemy import JSON, VARCHAR, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Admin/staff user that authenticates into the dashboard."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(VARCHAR(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(VARCHAR(200), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        VARCHAR(20), nullable=False, default=UserStatus.ACTIVE.value
    )
    role_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", name="fk_users_role_id_roles", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named role grouping a set of permissions."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(VARCHAR(80), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An atomic permission code, e.g. ``customers:read``."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Association of a role to a permission."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    role_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", name="fk_role_permissions_role_id_roles", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "permissions.id",
            name="fk_role_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed refresh token issued to a user session."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ApiKey(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Hashed API key for programmatic tenant access."""

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(VARCHAR(120), nullable=False)
    prefix: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, unique=True, index=True)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_api_keys_user_id_users", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
