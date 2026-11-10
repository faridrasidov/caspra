import csv
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import secrets

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.domain_errors import ConflictError, NotFoundError
from app.models.tenant.exports import ExportJob
from app.schemas.history import TransactionFilters
from app.schemas.transaction import TransactionOut
from app.services.arcade import ArcadeService
from app.services.history import HistoryService
from app.utils.idempotency import canonical_request_hash


class ExportService(ArcadeService):
    def path(self, filename):
        root = Path(settings.export_directory).resolve()
        target = (root / filename).resolve()
        if not target.is_relative_to(root) or target.parent != root:
            raise ValueError("Invalid export path")
        return target

    async def create(self, db, actor, payload):
        request_hash = canonical_request_hash(
            "export", **payload.model_dump(mode="json", exclude={"idempotency_key"})
        )
        row = (
            await db.execute(
                select(ExportJob).where(
                    ExportJob.tenant_id == actor.tenant_id,
                    ExportJob.creator_id == actor.id,
                    ExportJob.idempotency_key == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if row:
            if row.request_hash != request_hash:
                raise ConflictError("Export key was reused for another request")
            return row
        row = ExportJob(
            tenant_id=actor.tenant_id,
            creator_id=actor.id,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            filters=payload.filters.model_dump(mode="json"),
            format=payload.format,
            max_rows=payload.max_rows,
        )
        db.add(row)
        await db.commit()
        return row

    async def get_job(self, db, actor, job_id):
        row = await self.owned(db, ExportJob, actor.tenant_id, job_id)
        if row.creator_id != actor.id:
            raise NotFoundError("Export")
        return row

    async def download(self, db, actor, job_id):
        row = await self.get_job(db, actor, job_id)
        if row.status != "completed" or row.filename is None:
            raise ConflictError("Export is not ready")
        expires = (
            row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
        )
        if expires <= datetime.now(UTC):
            raise ConflictError("Export expired; request a new export")
        path = self.path(row.filename)
        if not path.is_file():
            raise NotFoundError("Export file")
        return path, row.format

    async def process_due(self, db):
        now = datetime.now(UTC)
        jobs = list(
            (
                await db.execute(
                    select(ExportJob.id)
                    .where(
                        or_(
                            ExportJob.status == "pending",
                            (ExportJob.status == "processing")
                            & (ExportJob.locked_at < now - timedelta(minutes=10)),
                        )
                    )
                    .limit(10)
                )
            ).scalars()
        )
        await db.commit()
        for job_id in jobs:
            await self.process(db, job_id)
        expired = list(
            (
                await db.execute(
                    select(ExportJob).where(
                        ExportJob.status == "completed", ExportJob.expires_at < now
                    )
                )
            ).scalars()
        )
        for row in expired:
            if row.filename:
                self.path(row.filename).unlink(missing_ok=True)
            row.status = "expired"
        await db.commit()

    async def process(self, db, job_id):
        row = (
            await db.execute(
                select(ExportJob).where(ExportJob.id == job_id).with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None or row.status not in {"pending", "processing"}:
            await db.rollback()
            return
        now = datetime.now(UTC)
        locked = row.locked_at
        if locked and locked.tzinfo is None:
            locked = locked.replace(tzinfo=UTC)
        if row.status == "processing" and locked and locked > now - timedelta(minutes=10):
            await db.rollback()
            return
        lease = secrets.token_hex(24)
        row.lease_token, row.status, row.locked_at = lease, "processing", now
        tenant_id, filters, fmt, maximum = (
            row.tenant_id,
            TransactionFilters.model_validate(row.filters),
            row.format,
            row.max_rows,
        )
        await db.commit()
        filename = f"{job_id.hex}-{lease}.{fmt}"
        path = self.path(filename)
        count, truncated, error = 0, False, None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            results = await db.stream_scalars(
                HistoryService()
                .query(tenant_id, filters)
                .limit(maximum + 1)
                .execution_options(yield_per=1000)
            )
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = None
                async for txn in results:
                    if count >= maximum:
                        truncated = True
                        break
                    item = TransactionOut.model_validate(txn).model_dump(mode="json")
                    if fmt == "csv":
                        if writer is None:
                            writer = csv.DictWriter(file, fieldnames=list(item))
                            writer.writeheader()
                        # Spreadsheet applications must not interpret descriptions as formulas.
                        writer.writerow(
                            {
                                key: "'" + value
                                if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                                else value
                                for key, value in item.items()
                            }
                        )
                    else:
                        file.write(json.dumps(item) + "\n")
                    count += 1
            await results.close()
        except (OSError, SQLAlchemyError, ValueError) as exc:
            error = f"Export failed ({type(exc).__name__})"
            path.unlink(missing_ok=True)
        await db.rollback()
        row = (
            await db.execute(select(ExportJob).where(ExportJob.id == job_id).with_for_update())
        ).scalar_one()
        if row.lease_token != lease:
            path.unlink(missing_ok=True)
            await db.rollback()
            return
        row.status = "failed" if error else "completed"
        row.error, row.row_count, row.truncated = error, count, truncated
        row.filename = None if error else filename
        row.expires_at = datetime.now(UTC) + timedelta(hours=24)
        row.lease_token = None
        await db.commit()
