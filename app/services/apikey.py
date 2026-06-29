# app/services/apikey.py

import hashlib
import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity.user import ApiKey
from app.schemas.apikey import ApiKeyCreate
from app.services.base import TenantScopedService


def _generate_key() -> tuple[str, str, str]:
    """Return (plaintext_key, prefix, sha256_hash)."""
    prefix = "csk_" + secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    plaintext = f"{prefix}.{secret}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, prefix, key_hash


class ApiKeyService(TenantScopedService):
    """Manage tenant API keys. Plaintext keys are shown only once on creation."""

    model = ApiKey
    resource_name = "API key"

    async def list_keys(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=ApiKey.created_at.desc())

    async def create_key(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID | None,
        payload: ApiKeyCreate,
    ) -> tuple[ApiKey, str]:
        plaintext, prefix, key_hash = _generate_key()
        api_key = ApiKey(
            tenant_id=tenant_id,
            name=payload.name,
            scopes=payload.scopes,
            prefix=prefix,
            key_hash=key_hash,
            user_id=user_id,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key, plaintext

    async def revoke_key(self, db: AsyncSession, tenant_id: UUID, key_id: UUID) -> ApiKey:
        api_key = await self.get_owned(db, key_id, tenant_id)
        api_key.revoked = True
        await db.commit()
        await db.refresh(api_key)
        return api_key

    async def regenerate_key(
        self, db: AsyncSession, tenant_id: UUID, key_id: UUID
    ) -> tuple[ApiKey, str]:
        api_key = await self.get_owned(db, key_id, tenant_id)
        plaintext, prefix, key_hash = _generate_key()
        api_key.prefix = prefix
        api_key.key_hash = key_hash
        api_key.revoked = False
        await db.commit()
        await db.refresh(api_key)
        return api_key, plaintext
