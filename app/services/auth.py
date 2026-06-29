# app/services/auth.py

from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models.identity.user import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserStatus,
)
from app.schemas.auth import TokenOut

REFRESH_TOKEN_EXPIRE_DAYS = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Authentication and session management for admin/staff users."""

    async def login(self, db: AsyncSession, email: str, password: str) -> TokenOut:
        """Validate credentials and issue an access + refresh token pair."""
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active")

        return await self._issue_tokens(db, user)

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenOut:
        """Exchange a valid refresh token for a new token pair."""
        token_hash = _hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(stmt)
        stored = result.scalars().first()

        if stored is None or stored.revoked:
            raise UnauthorizedError("Invalid or expired refresh token")

        # SQLite returns naive datetimes; normalise to UTC-aware before comparing.
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await db.get(User, stored.user_id)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active")

        stored.revoked = True
        return await self._issue_tokens(db, user)

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """Revoke the supplied refresh token (idempotent)."""
        token_hash = _hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(stmt)
        stored = result.scalars().first()
        if stored is not None and not stored.revoked:
            stored.revoked = True
            await db.commit()

    async def get_permissions(self, db: AsyncSession, user: User) -> list[str]:
        """Return the permission codes granted to the user's role."""
        if user.role_id is None:
            return []
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == user.role_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_role_name(self, db: AsyncSession, user: User) -> str | None:
        """Return the name of the user's role, if any."""
        if user.role_id is None:
            return None
        role = await db.get(Role, user.role_id)
        return role.name if role else None

    async def _issue_tokens(self, db: AsyncSession, user: User) -> TokenOut:
        access_token = create_access_token(str(user.id))
        raw_refresh = secrets.token_urlsafe(48)
        refresh_row = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(refresh_row)
        await db.commit()
        return TokenOut(access_token=access_token, refresh_token=raw_refresh)
