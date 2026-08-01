from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReconciliationIssue(BaseModel):
    kind: str
    resource_id: UUID
    currency: str | None = None
    expected_minor: int | None = None
    actual_minor: int | None = None
    difference_minor: int | None = None
    detail: str


class ReconciliationReportOut(BaseModel):
    healthy: bool
    generated_at: datetime
    checked_transactions: int
    checked_wallets: int
    issues: list[ReconciliationIssue]
