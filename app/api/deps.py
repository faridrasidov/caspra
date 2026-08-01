# app/api/deps.py

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import time
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_permissions import AdminPermission
from app.core.audit_context import bind_audit_actor
from app.core.config import settings
from app.core.domain_errors import ForbiddenError, ServiceUnavailableError, UnauthorizedError
from app.core.redis import get_redis_optional
from app.core.scopes import PublicScope
from app.core.security import (
    decrypt_device_secret,
    extract_token_subject,
    verify_device_signature,
    verify_device_signature_v2,
)
from app.models.device.device import Device, DeviceStatus
from app.models.identity.user import (
    ApiKey,
    Permission,
    Role,
    RolePermission,
    User,
    UserStatus,
)
from app.models.tenant.organization import Membership, MembershipStatus

bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_ROLE_NAMES = {"admin", "owner", "superadmin"}
_testing_device_nonces: dict[str, float] = {}


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
    if user.role_id is not None and await db.get(Role, user.role_id) is not None:
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
    return bool(names)


async def get_current_admin(
    current_user: Annotated[UUID, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> User:
    """Resolve and authorize the current admin user via a real role lookup."""
    user = await db.get(User, current_user)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise ForbiddenError("Admin access required")
    if not await _user_has_admin_role(db, user):
        raise ForbiddenError("Admin access required")
    request.state.actor_user_id = user.id
    request.state.tenant_id = user.tenant_id
    bind_audit_actor(user.id, user.tenant_id)
    return user


def require_admin_permission(permission: AdminPermission | str):
    required = str(permission)

    async def _guard(
        current_admin: Annotated[User, Depends(get_current_admin)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        role_ids: set[UUID] = set()
        if current_admin.role_id is not None:
            direct_role = await db.get(Role, current_admin.role_id)
            if direct_role is not None and direct_role.name in ADMIN_ROLE_NAMES:
                return current_admin
            role_ids.add(current_admin.role_id)

        membership_stmt = select(Membership.role_id).where(
            Membership.user_id == current_admin.id,
            Membership.tenant_id == current_admin.tenant_id,
            Membership.status == MembershipStatus.ACTIVE.value,
            Membership.role_id.is_not(None),
        )
        membership_role_ids = (await db.execute(membership_stmt)).scalars().all()
        role_ids.update(role_id for role_id in membership_role_ids if role_id is not None)
        if role_ids:
            admin_role_stmt = select(Role.name).where(Role.id.in_(role_ids))
            if any(
                name in ADMIN_ROLE_NAMES
                for name in (await db.execute(admin_role_stmt)).scalars().all()
            ):
                return current_admin

            permission_stmt = (
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(
                    RolePermission.role_id.in_(role_ids),
                    Permission.code == required,
                )
            )
            if (await db.execute(permission_stmt)).scalars().first() is not None:
                return current_admin
        raise ForbiddenError(f"Missing required permission: {required}")

    return _guard


async def get_current_device(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
    x_device_timestamp: Annotated[str | None, Header(alias="X-Device-Timestamp")] = None,
    x_device_signature: Annotated[str | None, Header(alias="X-Device-Signature")] = None,
    x_device_nonce: Annotated[str | None, Header(alias="X-Device-Nonce")] = None,
    x_device_signature_version: Annotated[
        str | None, Header(alias="X-Device-Signature-Version")
    ] = None,
) -> str:
    """Authenticate a reader/gateway via HMAC device headers."""
    if not x_device_id or not x_device_timestamp or not x_device_signature:
        raise UnauthorizedError("Device authentication required")

    try:
        device_uuid = UUID(x_device_id)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid device id") from exc
    device = await db.get(Device, device_uuid)
    if device is None:
        raise UnauthorizedError("Unknown device")
    if device.status != DeviceStatus.ACTIVE.value:
        raise ForbiddenError("Device is not active")

    _validate_device_timestamp(x_device_timestamp)
    body = await request.body()
    signature_version = x_device_signature_version or "1"
    if signature_version == "2":
        if not x_device_nonce or not 16 <= len(x_device_nonce) <= 128:
            raise UnauthorizedError("Valid device nonce required")
        if device.hmac_secret_encrypted is None:
            raise UnauthorizedError("Device has not been provisioned for HMAC v2")
        secrets_to_try = [decrypt_device_secret(device.hmac_secret_encrypted)]
        if _previous_device_secret_is_valid(device):
            secrets_to_try.append(
                decrypt_device_secret(device.hmac_previous_secret_encrypted or "")
            )
        valid = any(
            verify_device_signature_v2(
                secret=secret,
                method=request.method,
                path=request.url.path,
                device_id=x_device_id,
                timestamp=x_device_timestamp,
                nonce=x_device_nonce,
                body=body,
                signature=x_device_signature,
            )
            for secret in secrets_to_try
        )
        if not valid:
            raise UnauthorizedError("Invalid device signature")
        await _claim_device_nonce(device.id, x_device_nonce)
    elif signature_version == "1":
        if not _hmac_v1_is_enabled():
            raise UnauthorizedError("Device signature version 1 is no longer accepted")
        if not verify_device_signature(x_device_id, x_device_timestamp, body, x_device_signature):
            raise UnauthorizedError("Invalid device signature")
    else:
        raise UnauthorizedError("Unsupported device signature version")

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


def _validate_device_timestamp(raw_timestamp: str) -> None:
    if settings.testing:
        return
    try:
        timestamp = int(raw_timestamp)
    except ValueError as exc:
        raise UnauthorizedError("Invalid device timestamp") from exc
    current = int(datetime.now(UTC).timestamp())
    if abs(current - timestamp) > settings.device_signature_max_age_seconds:
        raise UnauthorizedError("Device signature timestamp is stale")


def _hmac_v1_is_enabled() -> bool:
    if not settings.device_hmac_v1_enabled:
        return False
    sunset = settings.device_hmac_v1_sunset_at
    return sunset is None or datetime.now(UTC) < sunset


def _previous_device_secret_is_valid(device: Device) -> bool:
    if device.hmac_previous_secret_encrypted is None or device.hmac_secret_rotated_at is None:
        return False
    rotated_at = device.hmac_secret_rotated_at
    if rotated_at.tzinfo is None:
        rotated_at = rotated_at.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - rotated_at).total_seconds()
    return age <= settings.device_previous_secret_grace_seconds


async def _claim_device_nonce(device_id: UUID, nonce: str) -> None:
    ttl = settings.device_signature_max_age_seconds
    redis_client = get_redis_optional()
    key = f"device_nonce:{device_id}:{nonce}"
    if redis_client is not None:
        claimed = await redis_client.set(key, "1", nx=True, ex=ttl)
        if not claimed:
            raise UnauthorizedError("Device signature replay detected")
        return
    if not settings.testing:
        raise ServiceUnavailableError("Device replay protection is unavailable")

    now = time.monotonic()
    expired = [item for item, expires_at in _testing_device_nonces.items() if expires_at <= now]
    for item in expired:
        _testing_device_nonces.pop(item, None)
    if key in _testing_device_nonces:
        raise UnauthorizedError("Device signature replay detected")
    _testing_device_nonces[key] = now + ttl


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
