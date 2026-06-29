# app/schemas/wallet.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ledger.wallet import WalletStatus, WalletType
from app.schemas import PaginationSchema


class WalletBase(BaseModel):
    customer_id: UUID
    currency: str = Field(..., min_length=3, max_length=3)
    type: WalletType = WalletType.CREDIT


class WalletCreate(WalletBase):
    model_config = ConfigDict(extra="forbid")


class WalletOut(WalletBase):
    id: UUID
    tenant_id: UUID
    balance_minor: int
    status: WalletStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedWalletOut(PaginationSchema):
    items: list[WalletOut]


class WalletBalanceOut(BaseModel):
    wallet_id: UUID
    currency: str
    balance_minor: int

    model_config = ConfigDict(from_attributes=True)


# ========== Money Operation Requests (idempotent) ==========


class WalletTopupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    description: str | None = Field(None, max_length=500)


class WalletDeductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    description: str | None = Field(None, max_length=500)


class WalletTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_wallet_id: UUID
    to_wallet_id: UUID
    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    description: str | None = Field(None, max_length=500)
