# app/utils/pagination.py

import math
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate_async_query(
    *,
    session: AsyncSession,
    base_query: Select[Any],
    page: int,
    limit: int,
    count_query: Select[Any] | None = None,
    use_scalars: bool = False,
) -> dict[str, Any]:
    """Execute a paginated async query and return {page, total, pages, items}."""
    if count_query is None:
        count_query = select(func.count()).select_from(base_query.subquery())

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * limit
    paginated_query = base_query.offset(offset).limit(limit)
    result = await session.execute(paginated_query)

    items = list(result.scalars().all()) if use_scalars else list(result.all())

    pages = math.ceil(total / limit) if limit else 0
    return {"page": page, "total": total, "pages": pages, "items": items}
