# app/utils/idempotency.py

from datetime import date, datetime
import enum
import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError


def canonical_request_hash(operation: str, **values) -> str:
    """Create a stable fingerprint for an idempotent operation."""

    def normalize(value):
        if isinstance(value, (UUID, date, datetime, enum.Enum)):
            return str(value)
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        return value

    payload = {"operation": operation, **values}
    encoded = json.dumps(
        normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def find_existing_by_idempotency_key(
    db: AsyncSession,
    model: type,
    idempotency_key: UUID,
    tenant_id: UUID,
    request_hash: str | None = None,
):
    """Lock and return an existing row for a replayed idempotency key, if any.

    PostgreSQL's unique constraint remains the source of truth, while the
    transaction-scoped advisory lock closes the check-then-insert race between
    concurrent requests using the same tenant/key pair. Hash collisions only
    serialize unrelated requests; they cannot change ledger results.
    """
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        lock_digest = hashlib.sha256(tenant_id.bytes + idempotency_key.bytes).digest()
        lock_key = int.from_bytes(lock_digest[:8], byteorder="big", signed=True)
        await db.execute(select(func.pg_advisory_xact_lock(lock_key)))

    stmt = select(model).where(
        model.idempotency_key == idempotency_key,  # type: ignore[attr-defined]
        model.tenant_id == tenant_id,  # type: ignore[attr-defined]
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing is not None and request_hash is not None:
        existing_hash = getattr(existing, "request_hash", None)
        if existing_hash is not None and existing_hash != request_hash:
            raise ConflictError(
                "Idempotency key was already used for a different request",
                code="idempotency_conflict",
            )
    return existing
