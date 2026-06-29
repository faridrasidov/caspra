# app/services/device_card.py

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError, NotFoundError, ValidationError
from app.models.device.device import Card, CardStatus
from app.models.ledger.hold import TempCardAssignment
from app.models.ledger.wallet import Wallet, WalletStatus, WalletType
from app.schemas.device_card import (
    CardBalanceOut,
    CardInfoOut,
    CardVerifyOut,
    WalletBalanceMini,
)


class DeviceCardService:
    """Reader-facing card lookups, scoped strictly to the device's tenant."""

    async def get_card_by_uid(self, db: AsyncSession, tenant_id: UUID, card_uid: str) -> Card:
        """Resolve a card by UID within the tenant or raise ``NotFoundError``."""
        stmt = select(Card).where(Card.tenant_id == tenant_id, Card.uid == card_uid)
        card = (await db.execute(stmt)).scalars().first()
        if card is None:
            raise NotFoundError("Card", card_uid)
        return card

    async def verify(self, db: AsyncSession, tenant_id: UUID, card_uid: str) -> CardVerifyOut:
        card = await self.get_card_by_uid(db, tenant_id, card_uid)
        blocked = card.status in (CardStatus.BLOCKED.value, CardStatus.LOST.value)
        return CardVerifyOut(
            card_id=card.id,
            uid=card.uid,
            status=card.status,
            valid=card.status == CardStatus.ACTIVE.value,
            blocked=blocked,
            expired=False,
        )

    async def info(self, db: AsyncSession, tenant_id: UUID, card_uid: str) -> CardInfoOut:
        card = await self.get_card_by_uid(db, tenant_id, card_uid)
        return CardInfoOut(
            card_id=card.id,
            uid=card.uid,
            type=card.type,
            status=card.status,
            customer_id=card.customer_id,
        )

    async def balance(self, db: AsyncSession, tenant_id: UUID, card_uid: str) -> CardBalanceOut:
        card = await self.get_card_by_uid(db, tenant_id, card_uid)
        balances: list[WalletBalanceMini] = []
        if card.customer_id is not None:
            stmt = select(Wallet).where(
                Wallet.tenant_id == tenant_id, Wallet.customer_id == card.customer_id
            )
            balances = [
                WalletBalanceMini(
                    wallet_id=wallet.id,
                    type=wallet.type,
                    currency=wallet.currency,
                    balance_minor=wallet.balance_minor,
                )
                for wallet in (await db.execute(stmt)).scalars().all()
            ]
        return CardBalanceOut(card_id=card.id, customer_id=card.customer_id, balances=balances)

    async def resolve_wallet(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        card: Card,
        wallet_type: WalletType,
        currency: str,
    ) -> Wallet:
        """Find the active wallet a charge/preauth should hit for this card."""
        if card.status != CardStatus.ACTIVE.value:
            raise ValidationError(f"Card is not active (status: {card.status})")
        if card.customer_id is None:
            raise ValidationError("Card is not assigned to a customer")
        stmt = select(Wallet).where(
            Wallet.tenant_id == tenant_id,
            Wallet.customer_id == card.customer_id,
            Wallet.type == wallet_type.value,
            Wallet.currency == currency,
        )
        wallet = (await db.execute(stmt)).scalars().first()
        if wallet is None:
            raise NotFoundError("Wallet", f"{wallet_type.value}/{currency}")
        if wallet.status != WalletStatus.ACTIVE.value:
            raise ValidationError(f"Wallet is not active (status: {wallet.status})")
        return wallet

    async def assign_temp(
        self, db: AsyncSession, tenant_id: UUID, card_uid: str, session_ref: str | None
    ) -> TempCardAssignment:
        """Assign an anonymous temporary card to a session (idempotent on active)."""
        card = await self.get_card_by_uid(db, tenant_id, card_uid)
        existing = await self._active_assignment(db, tenant_id, card.id)
        if existing is not None:
            raise ConflictError("Card already has an active temporary assignment")
        assignment = TempCardAssignment(
            tenant_id=tenant_id, card_id=card.id, session_ref=session_ref, active=True
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)
        return assignment

    async def unassign_temp(
        self, db: AsyncSession, tenant_id: UUID, card_uid: str
    ) -> TempCardAssignment:
        card = await self.get_card_by_uid(db, tenant_id, card_uid)
        assignment = await self._active_assignment(db, tenant_id, card.id)
        if assignment is None:
            raise NotFoundError("Active temporary assignment", card_uid)
        assignment.active = False
        assignment.released_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(assignment)
        return assignment

    async def _active_assignment(
        self, db: AsyncSession, tenant_id: UUID, card_id: UUID
    ) -> TempCardAssignment | None:
        stmt = select(TempCardAssignment).where(
            TempCardAssignment.tenant_id == tenant_id,
            TempCardAssignment.card_id == card_id,
            TempCardAssignment.active.is_(True),
        )
        return (await db.execute(stmt)).scalars().first()
