# app/services/card.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError, NotFoundError
from app.models.device.device import Card, CardStatus
from app.models.ledger.wallet import Customer
from app.schemas.card import CardCreate
from app.services.base import TenantScopedService


class CardService(TenantScopedService):
    """Manage RFID/NFC cards and their lifecycle within a tenant."""

    model = Card
    resource_name = "Card"

    async def list_cards(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Card.created_at.desc())

    async def register_card(self, db: AsyncSession, tenant_id: UUID, payload: CardCreate) -> Card:
        await self._assert_uid_free(db, tenant_id, payload.uid)
        if payload.customer_id is not None:
            await self._assert_customer_exists(db, tenant_id, payload.customer_id)
        card = Card(
            tenant_id=tenant_id,
            uid=payload.uid,
            type=payload.type.value,
            customer_id=payload.customer_id,
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)
        return card

    async def get_card(self, db: AsyncSession, tenant_id: UUID, card_id: UUID) -> Card:
        return await self.get_owned(db, card_id, tenant_id)

    async def assign(
        self, db: AsyncSession, tenant_id: UUID, card_id: UUID, customer_id: UUID
    ) -> Card:
        card = await self.get_owned(db, card_id, tenant_id)
        await self._assert_customer_exists(db, tenant_id, customer_id)
        card.customer_id = customer_id
        await db.commit()
        await db.refresh(card)
        return card

    async def unassign(self, db: AsyncSession, tenant_id: UUID, card_id: UUID) -> Card:
        card = await self.get_owned(db, card_id, tenant_id)
        card.customer_id = None
        await db.commit()
        await db.refresh(card)
        return card

    async def set_status(
        self, db: AsyncSession, tenant_id: UUID, card_id: UUID, new_status: CardStatus
    ) -> Card:
        card = await self.get_owned(db, card_id, tenant_id)
        card.status = new_status.value
        await db.commit()
        await db.refresh(card)
        return card

    async def reset(self, db: AsyncSession, tenant_id: UUID, card_id: UUID) -> Card:
        """Reset a card to active and unassigned."""
        card = await self.get_owned(db, card_id, tenant_id)
        card.status = CardStatus.ACTIVE.value
        card.customer_id = None
        await db.commit()
        await db.refresh(card)
        return card

    async def replace(self, db: AsyncSession, tenant_id: UUID, card_id: UUID, new_uid: str) -> Card:
        """Block the old card and issue a replacement with the same customer."""
        old = await self.get_owned(db, card_id, tenant_id)
        await self._assert_uid_free(db, tenant_id, new_uid)
        old.status = CardStatus.LOST.value
        replacement = Card(
            tenant_id=tenant_id,
            uid=new_uid,
            type=old.type,
            customer_id=old.customer_id,
        )
        db.add(replacement)
        await db.commit()
        await db.refresh(replacement)
        return replacement

    async def _assert_uid_free(self, db: AsyncSession, tenant_id: UUID, uid: str) -> None:
        stmt = select(Card.id).where(Card.tenant_id == tenant_id, Card.uid == uid)
        if (await db.execute(stmt)).first() is not None:
            raise ConflictError(f"Card with uid '{uid}' already exists")

    async def _assert_customer_exists(
        self, db: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> None:
        stmt = select(Customer.id).where(
            Customer.id == customer_id, Customer.tenant_id == tenant_id
        )
        if (await db.execute(stmt)).first() is None:
            raise NotFoundError("Customer", str(customer_id))
