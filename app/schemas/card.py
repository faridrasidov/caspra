# app/schemas/card.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import CardStatus, CardType
from app.schemas import PaginationSchema


class CardBase(BaseModel):
    uid: str = Field(..., min_length=1, max_length=120)
    type: CardType = CardType.RFID


class CardCreate(CardBase):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None


class CardOut(CardBase):
    id: UUID
    tenant_id: UUID
    status: CardStatus
    customer_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedCardOut(PaginationSchema):
    items: list[CardOut]


class CardAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID


class CardReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_uid: str = Field(..., min_length=1, max_length=120)
