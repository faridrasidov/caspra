# app/utils/idempotency.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def find_existing_by_idempotency_key(
    db: AsyncSession,
    model: type,
    idempotency_key: UUID,
    tenant_id: UUID,
):
    """Return an existing row for a replayed idempotency key, if any."""
    stmt = select(model).where(
        model.idempotency_key == idempotency_key,  # type: ignore[attr-defined]
        model.tenant_id == tenant_id,  # type: ignore[attr-defined]
    )
    result = await db.execute(stmt)
    return result.scalars().first()
