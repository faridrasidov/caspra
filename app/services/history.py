from __future__ import annotations

import base64
from datetime import datetime
import json
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select, tuple_

from app.core.domain_errors import ValidationError
from app.models.ledger.wallet import Transaction
from app.utils.idempotency import canonical_request_hash

if TYPE_CHECKING:
    from app.schemas.history import TransactionFilters


class HistoryService:
    def query(self, tenant_id, filters: TransactionFilters):
        stmt = select(Transaction).where(Transaction.tenant_id == tenant_id)
        for key in ("status", "currency", "customer_id", "wallet_id", "device_id", "location_id"):
            value = getattr(filters, key)
            if value is not None:
                stmt = stmt.where(getattr(Transaction, key) == value)
        if filters.start:
            stmt = stmt.where(Transaction.created_at >= filters.start)
        if filters.end:
            stmt = stmt.where(Transaction.created_at < filters.end)
        if filters.q:
            value = filters.q.strip()
            try:
                identifier = UUID(value)
                stmt = stmt.where(
                    or_(
                        *[
                            getattr(Transaction, column) == identifier
                            for column in ("id", "wallet_id", "customer_id", "device_id")
                        ]
                    )
                )
            except ValueError:
                escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(
                    or_(
                        Transaction.description.ilike(f"%{escaped}%", escape="\\"),
                        cast(Transaction.id, String).ilike(f"{escaped}%", escape="\\"),
                    )
                )
        return stmt.order_by(Transaction.created_at.desc(), Transaction.id.desc())

    async def history(self, db, tenant_id, filters, *, cursor=None, limit=20):
        stmt = self.query(tenant_id, filters)
        fingerprint = canonical_request_hash(
            "history", tenant_id=tenant_id, **filters.model_dump(mode="json")
        )
        total = int(
            (
                await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
            ).scalar_one()
        )
        page = 1
        sqlite = db.bind.dialect.name == "sqlite"
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
                if decoded["filter"] != fingerprint:
                    raise ValueError("Filter changed")
                when = datetime.fromisoformat(decoded["at"])
                identifier = UUID(decoded["id"])
                page = int(decoded["page"]) + 1
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValidationError("Invalid history cursor") from exc
            time_column = cast(Transaction.created_at, String) if sqlite else Transaction.created_at
            boundary = decoded["sort"] if sqlite else when
            stmt = stmt.where(tuple_(time_column, Transaction.id) < (boundary, identifier))
        rows = list((await db.execute(stmt.limit(limit + 1))).scalars())
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            raw_time = (
                await db.scalar(
                    select(cast(Transaction.created_at, String)).where(Transaction.id == last.id)
                )
                if sqlite
                else last.created_at.isoformat()
            )
            next_cursor = (
                base64.urlsafe_b64encode(
                    json.dumps(
                        {
                            "at": last.created_at.isoformat(),
                            "sort": raw_time,
                            "id": str(last.id),
                            "filter": fingerprint,
                            "page": page,
                        }
                    ).encode()
                )
                .decode()
                .rstrip("=")
            )
        return {
            "items": rows[:limit],
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "next_cursor": next_cursor,
        }
