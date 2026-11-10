from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.arcade import Input, RecordOut


class TransactionFilters(Input):
    q: str | None = Field(None, max_length=200)
    status: Literal["pending", "posted", "failed", "reversed"] | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    customer_id: UUID | None = None
    device_id: UUID | None = None
    location_id: UUID | None = None
    wallet_id: UUID | None = None
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start and self.end and self.end <= self.start:
            raise ValueError("End timestamp must follow start")
        return self


class ExportRequest(Input):
    filters: TransactionFilters = Field(default_factory=TransactionFilters)
    format: Literal["csv", "jsonl"] = "csv"
    max_rows: int = Field(1000000, ge=1, le=1000000)
    idempotency_key: UUID


class ExportOut(RecordOut):
    status: str
    format: str
    row_count: int
    truncated: bool
    expires_at: datetime | None
    error: str | None
