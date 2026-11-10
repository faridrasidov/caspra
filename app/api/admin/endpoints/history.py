from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import AwareDatetime
from pydantic import ValidationError as SchemaError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin_permission
from app.core.admin_permissions import AdminPermission
from app.core.domain_errors import ValidationError
from app.models.identity.user import User
from app.schemas.arcade import Page
from app.schemas.history import ExportOut, ExportRequest, TransactionFilters
from app.schemas.transaction import TransactionOut
from app.services.exports import ExportService
from app.services.history import HistoryService

router = APIRouter(tags=["admin-history"])
DB = Annotated[AsyncSession, Depends(get_db)]
Reader = Annotated[User, Depends(require_admin_permission(AdminPermission.TRANSACTIONS_READ))]


@router.get("/transactions/history", response_model=Page[TransactionOut])
async def history(
    db: DB,
    actor: Reader,
    cursor: str | None = Query(None, max_length=2048),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    status: Literal["pending", "posted", "failed", "reversed"] | None = None,
    currency: str | None = None,
    customer_id: UUID | None = None,
    device_id: UUID | None = None,
    location_id: UUID | None = None,
    wallet_id: UUID | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
):
    try:
        filters = TransactionFilters(
            q=q,
            status=status,
            currency=currency,
            customer_id=customer_id,
            device_id=device_id,
            location_id=location_id,
            wallet_id=wallet_id,
            start=start,
            end=end,
        )
    except SchemaError as exc:
        raise ValidationError("Invalid history filters or date range") from exc
    return await HistoryService().history(db, actor.tenant_id, filters, cursor=cursor, limit=limit)


@router.post("/exports", response_model=ExportOut, status_code=202)
async def create_export(payload: ExportRequest, db: DB, actor: Reader):
    return await ExportService().create(db, actor, payload)


@router.get("/exports/{job_id}", response_model=ExportOut)
async def export_status(job_id: UUID, db: DB, actor: Reader):
    return await ExportService().get_job(db, actor, job_id)


@router.get("/exports/{job_id}/download", response_class=FileResponse)
async def download_export(job_id: UUID, db: DB, actor: Reader):
    path, fmt = await ExportService().download(db, actor, job_id)
    return FileResponse(
        path,
        media_type="text/csv" if fmt == "csv" else "application/x-ndjson",
        filename=f"transactions.{fmt}",
        headers={"Cache-Control": "no-store"},
    )
