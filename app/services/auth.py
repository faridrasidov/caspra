# app/services/auth.py

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_permissions import all_admin_permissions
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

        tokens, _ = await self._issue_tokens(db, user, family_id=uuid4())
        await db.commit()
        return tokens

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenOut:
        """Exchange a valid refresh token for a new token pair."""
        token_hash = _hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        result = await db.execute(stmt)
        stored = result.scalars().first()

        if stored is None:
            raise UnauthorizedError("Invalid or expired refresh token")
        if stored.revoked:
            await self._revoke_family(db, stored.family_id)
            raise UnauthorizedError("Refresh token reuse detected; session revoked")

        # SQLite returns naive datetimes; normalise to UTC-aware before comparing.
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            await self._revoke_family(db, stored.family_id)
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await db.get(User, stored.user_id)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active")

        stored.revoked = True
        stored.revoked_at = datetime.now(UTC)
        tokens, replacement = await self._issue_tokens(db, user, family_id=stored.family_id)
        stored.replaced_by_id = replacement.id
        await db.commit()
        return tokens

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """Revoke the supplied refresh token (idempotent)."""
        token_hash = _hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(stmt)
        stored = result.scalars().first()
        if stored is not None:
            await self._revoke_family(db, stored.family_id)

    async def revoke_all_sessions(self, db: AsyncSession, user_id: UUID) -> None:
        now = datetime.now(UTC)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True, revoked_at=now)
        )
        await db.commit()

    async def get_permissions(self, db: AsyncSession, user: User) -> list[str]:
        """Return the permission codes granted to the user's role."""
        if user.role_id is None:
            return []
        role = await db.get(Role, user.role_id)
        if role is not None and role.name in {"admin", "owner", "superadmin"}:
            return all_admin_permissions()
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

    async def _issue_tokens(
        self, db: AsyncSession, user: User, *, family_id: UUID
    ) -> tuple[TokenOut, RefreshToken]:
        access_token = create_access_token(str(user.id))
        raw_refresh = secrets.token_urlsafe(48)
        refresh_row = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh),
            family_id=family_id,
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(refresh_row)
        await db.flush()
        return (
            TokenOut(access_token=access_token, refresh_token=raw_refresh),
            refresh_row,
        )

    async def _revoke_family(self, db: AsyncSession, family_id: UUID) -> None:
        now = datetime.now(UTC)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked.is_(False))
            .values(revoked=True, revoked_at=now)
        )
        await db.commit()
