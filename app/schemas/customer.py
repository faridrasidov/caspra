# app/schemas/customer.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ledger.wallet import CustomerStatus
from app.schemas import PaginationSchema


class CustomerBase(BaseModel):
    external_id: str | None = Field(None, max_length=120)
    full_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=40)


class CustomerCreate(CustomerBase):
    model_config = ConfigDict(extra="forbid")


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(None, max_length=120)
    full_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=40)
    status: CustomerStatus | None = None


class CustomerOut(CustomerBase):
    id: UUID
    tenant_id: UUID
    status: CustomerStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedCustomerOut(PaginationSchema):
    items: list[CustomerOut]


class CustomerImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customers: list[CustomerCreate] = Field(..., min_length=1, max_length=1000)


class CustomerImportResult(BaseModel):
    created: int
    skipped: int


class WalletBalanceOut(BaseModel):
    wallet_id: UUID
    currency: str
    balance_minor: int
    type: str

    model_config = ConfigDict(from_attributes=True)


class CustomerBalancesOut(BaseModel):
    customer_id: UUID
    balances: list[WalletBalanceOut]
