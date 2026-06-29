# app/api/deps.py

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.domain_errors import ForbiddenError, UnauthorizedError
from app.core.redis import get_redis_optional
from app.core.scopes import PublicScope
from app.core.security import extract_token_subject, verify_device_signature
from app.models.device.device import Device, DeviceStatus
from app.models.identity.user import ApiKey, Role, User, UserStatus
from app.models.tenant.organization import Membership, MembershipStatus

bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_ROLE_NAMES = {"admin", "owner", "superadmin"}


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UUID:
    """Resolve the authenticated user ID from a JWT bearer token."""
    if credentials is None:
        raise UnauthorizedError
    try:
        return UUID(extract_token_subject(credentials.credentials))
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid credentials") from exc


async def _user_has_admin_role(db: AsyncSession, user: User) -> bool:
    """True if the user holds an admin-level role directly or via a membership."""
    if user.role_id is not None:
        role = await db.get(Role, user.role_id)
        if role is not None and role.name in ADMIN_ROLE_NAMES:
            return True

    stmt = (
        select(Role.name)
        .join(Membership, Membership.role_id == Role.id)
        .where(
            Membership.user_id == user.id,
            Membership.tenant_id == user.tenant_id,
            Membership.status == MembershipStatus.ACTIVE.value,
        )
    )
    names = (await db.execute(stmt)).scalars().all()
    return any(name in ADMIN_ROLE_NAMES for name in names)


async def get_current_admin(
    current_user: Annotated[UUID, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve and authorize the current admin user via a real role lookup."""
    user = await db.get(User, current_user)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise ForbiddenError("Admin access required")
    if not await _user_has_admin_role(db, user):
        raise ForbiddenError("Admin access required")
    return user


async def get_current_device(
    request: Request,
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
    x_device_timestamp: Annotated[str | None, Header(alias="X-Device-Timestamp")] = None,
    x_device_signature: Annotated[str | None, Header(alias="X-Device-Signature")] = None,
) -> str:
    """Authenticate a reader/gateway via HMAC device headers."""
    if not x_device_id or not x_device_timestamp or not x_device_signature:
        raise UnauthorizedError("Device authentication required")

    body = await request.body()
    if not verify_device_signature(x_device_id, x_device_timestamp, body, x_device_signature):
        raise UnauthorizedError("Invalid device signature")

    return x_device_id


async def get_authenticated_device(
    device_id: Annotated[str, Depends(get_current_device)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Device:
    """Resolve the HMAC-authenticated device and assert it is active.

    The device record is the source of truth for tenant scoping — every device
    route must use ``device.tenant_id`` and never trust a reader-supplied tenant.
    """
    try:
        device_uuid = UUID(device_id)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid device id") from exc

    device = await db.get(Device, device_uuid)
    if device is None:
        raise UnauthorizedError("Unknown device")
    if device.status != DeviceStatus.ACTIVE.value:
        raise ForbiddenError("Device is not active")
    return device


# ========== Public Developer API (scoped API keys) ==========


@dataclass(slots=True)
class ApiKeyContext:
    """Resolved identity for a public API caller.

    The API key is the single source of truth for tenant scoping on the public
    surface — every query MUST filter by ``tenant_id`` from this context and
    never trust a caller-supplied tenant value.
    """

    api_key_id: UUID
    tenant_id: UUID
    scopes: frozenset[str] = field(default_factory=frozenset)

    def has_scope(self, scope: PublicScope | str) -> bool:
        return str(scope) in self.scopes


async def get_api_key(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyContext:
    """Authenticate a third-party developer via a scoped API key.

    Accepts the key as ``Authorization: Bearer <key>`` or ``X-API-Key``. The
    key is hashed (SHA-256, matching ``ApiKeyService``) and looked up; admin
    JWTs and device HMAC are never accepted on this surface.
    """
    raw_key = credentials.credentials if credentials is not None else x_api_key
    if not raw_key:
        raise UnauthorizedError("API key required")

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
    api_key = (await db.execute(stmt)).scalars().first()
    if api_key is None or api_key.revoked:
        raise UnauthorizedError("Invalid API key")

    api_key.last_used_at = datetime.now(UTC)
    await db.commit()

    return ApiKeyContext(
        api_key_id=api_key.id,
        tenant_id=api_key.tenant_id,
        scopes=frozenset(api_key.scopes or []),
    )


def require_scope(scope: PublicScope | str):
    """Return a dependency that 403s if the API key lacks ``scope``."""
    required = str(scope)

    async def _guard(
        ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
    ) -> ApiKeyContext:
        if required not in ctx.scopes:
            raise ForbiddenError(f"Missing required scope: {required}")
        return ctx

    return _guard


async def rate_limit_public(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
) -> None:
    """Per-key fixed-window rate limit backed by Redis.

    No-op when Redis is unavailable (e.g. the test suite / ``memory://``), so
    this never breaks local or CI runs. TODO: enforce in production once a
    shared Redis is provisioned for all workers.
    """
    redis_client = get_redis_optional()
    if redis_client is None:
        return

    window = int(datetime.now(UTC).timestamp() // 60)
    redis_key = f"public_ratelimit:{ctx.api_key_id}:{window}"
    count = await redis_client.incr(redis_key)
    if count == 1:
        await redis_client.expire(redis_key, 60)
    if count > settings.public_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
