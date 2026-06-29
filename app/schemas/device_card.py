# app/schemas/device_card.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import CardStatus, CardType
from app.models.ledger.wallet import WalletType


class CardUidRequest(BaseModel):
    """Reader-supplied card UID lookup body."""

    model_config = ConfigDict(extra="forbid")

    card_uid: str = Field(..., min_length=1, max_length=120)


class CardVerifyOut(BaseModel):
    card_id: UUID
    uid: str
    status: CardStatus
    valid: bool
    blocked: bool
    expired: bool


class CardInfoOut(BaseModel):
    card_id: UUID
    uid: str
    type: CardType
    status: CardStatus
    customer_id: UUID | None = None


class WalletBalanceMini(BaseModel):
    wallet_id: UUID
    type: WalletType
    currency: str
    balance_minor: int


class CardBalanceOut(BaseModel):
    card_id: UUID
    customer_id: UUID | None = None
    balances: list[WalletBalanceMini]


class TempAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_uid: str = Field(..., min_length=1, max_length=120)
    session_ref: str | None = Field(None, max_length=120)


class TempAssignmentOut(BaseModel):
    id: UUID
    card_id: UUID
    session_ref: str | None = None
    active: bool

    model_config = ConfigDict(from_attributes=True)
