from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from sqlalchemy import select

from app.core.domain_errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.engines.pricing import PricingEngine
from app.models.catalog.arcade import Machine, PlaySession, PriceRevision, PricingSchedule
from app.models.device.device import Card, Device
from app.models.ledger.wallet import Customer, Transaction, Wallet
from app.models.tenant.organization import Location, OrgSettings
from app.models.tenant.venue import FamilyRelationship, Receipt, SpendingLimit
from app.schemas.arcade import (
    CustomerWorkspace,
    MachineCreate,
    MachineUpdate,
    PlayRequest,
    PricingScheduleCreate,
)
from app.services.audit import AuditService
from app.services.base import TenantScopedService
from app.services.ledger import LedgerService
from app.utils.idempotency import canonical_request_hash

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.identity.user import User


class ArcadeService(TenantScopedService):
    model = Machine
    resource_name = "Machine"

    async def owned(self, db, model, tenant_id, obj_id, *, lock=False):
        stmt = select(model).where(model.id == obj_id, model.tenant_id == tenant_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(model.__name__, str(obj_id))
        return row

    async def timezone(self, db, tenant_id, location_id=None):
        if location_id:
            return (await self.owned(db, Location, tenant_id, location_id)).timezone
        row = (
            (await db.execute(select(OrgSettings).where(OrgSettings.tenant_id == tenant_id)))
            .scalars()
            .first()
        )
        return row.timezone if row else "UTC"

    async def list_records(self, db, model, tenant_id, page=1, limit=20, *, filters=(), q=None):
        service = TenantScopedService()
        service.model = model
        return await service.paginate(
            db, tenant_id, page, limit, *filters, order_by=model.created_at.desc(), q=q
        )

    async def create_machine(self, db: AsyncSession, tenant_id: UUID, payload: MachineCreate):
        reader = await self.owned(db, Device, tenant_id, payload.device_id, lock=True)
        if reader.type != "reader" or reader.status != "active":
            raise ValidationError("Assign an active reader")
        if payload.location_id:
            await self.owned(db, Location, tenant_id, payload.location_id)
        if (await db.execute(select(Machine.id).where(Machine.device_id == reader.id))).first():
            raise ConflictError("Reader already belongs to a machine")
        machine = Machine(tenant_id=tenant_id, **payload.model_dump())
        db.add(machine)
        await db.flush()
        db.add(
            PriceRevision(
                tenant_id=tenant_id,
                machine_id=machine.id,
                revision=1,
                price_minor=machine.price_minor,
                currency=machine.currency,
            )
        )
        await db.commit()
        return machine

    async def update_machine(self, db, tenant_id, machine_id, payload: MachineUpdate):
        machine = await self.owned(db, Machine, tenant_id, machine_id, lock=True)
        changes = payload.model_dump(exclude_unset=True)
        if any(value is None for value in changes.values()):
            raise ValidationError("Machine fields cannot be cleared")
        if "price_minor" in changes and changes["price_minor"] != machine.price_minor:
            machine.price_revision += 1
            db.add(
                PriceRevision(
                    tenant_id=tenant_id,
                    machine_id=machine.id,
                    revision=machine.price_revision,
                    price_minor=changes["price_minor"],
                    currency=machine.currency,
                )
            )
        for key, value in changes.items():
            setattr(machine, key, value)
        await db.commit()
        return machine

    async def create_schedule(self, db, tenant_id, payload: PricingScheduleCreate):
        machine = await self.owned(db, Machine, tenant_id, payload.machine_id, lock=True)
        if payload.start_minute >= payload.end_minute:
            raise ValidationError("Schedule end must follow start; split overnight schedules")
        overlap = select(PricingSchedule.id).where(
            PricingSchedule.tenant_id == tenant_id,
            PricingSchedule.machine_id == payload.machine_id,
            PricingSchedule.active.is_(True),
            PricingSchedule.weekday == payload.weekday,
            PricingSchedule.start_minute < payload.end_minute,
            PricingSchedule.end_minute > payload.start_minute,
        )
        if (await db.execute(overlap)).first():
            raise ConflictError("Pricing schedules cannot overlap")
        row = PricingSchedule(
            tenant_id=tenant_id, currency=machine.currency, **payload.model_dump()
        )
        db.add(row)
        await db.commit()
        return row

    async def disable_schedule(self, db, tenant_id, schedule_id):
        row = await self.owned(db, PricingSchedule, tenant_id, schedule_id)
        await self.owned(db, Machine, tenant_id, row.machine_id, lock=True)
        row.active = False
        await db.commit()

    async def price(self, db, machine, now):
        timezone = await self.timezone(db, machine.tenant_id, machine.location_id)
        return await PricingEngine().resolve_machine_price(db, machine, now, timezone)

    async def authorize(self, db, device: Device, payload: PlayRequest):
        machine = (
            await db.execute(
                select(Machine)
                .where(Machine.tenant_id == device.tenant_id, Machine.device_id == device.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if machine is None:
            raise NotFoundError("Machine for reader")
        request_hash = canonical_request_hash(
            "play", device_id=device.id, card_uid=payload.card_uid
        )
        existing = (
            await db.execute(
                select(PlaySession).where(
                    PlaySession.tenant_id == device.tenant_id,
                    PlaySession.idempotency_key == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Idempotency key was reused", code="idempotency_conflict")
            return existing
        if machine.state != "available":
            raise ConflictError("Machine is not available")
        card = (
            await db.execute(
                select(Card)
                .where(Card.tenant_id == device.tenant_id, Card.uid == payload.card_uid)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if card is None or card.status != "active" or card.customer_id is None:
            raise ValidationError("Card must be active and assigned")
        customer = await self.owned(db, Customer, device.tenant_id, card.customer_id, lock=True)
        if customer.status != "active":
            raise ForbiddenError("Customer is not active")
        now = datetime.now(UTC)
        snapshot = await self.price(db, machine, now)
        txn = await LedgerService(commit=False).charge_customer(
            db,
            device.tenant_id,
            customer.id,
            amount_minor=snapshot["amount_minor"],
            currency=machine.currency,
            idempotency_key=payload.idempotency_key,
            device_id=device.id,
            description=f"Machine play {machine.id}",
        )
        txn.location_id = machine.location_id
        play = PlaySession(
            tenant_id=device.tenant_id,
            machine_id=machine.id,
            device_id=device.id,
            customer_id=customer.id,
            card_id=card.id,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            transaction_id=txn.id,
            amount_minor=txn.amount_minor,
            currency=txn.currency,
            price_snapshot=snapshot,
            execute_before=now + timedelta(seconds=30),
        )
        db.add(play)
        await db.commit()
        return play

    async def device_play(self, db, device, play_id):
        play = await self.owned(db, PlaySession, device.tenant_id, play_id)
        if play.device_id != device.id:
            raise NotFoundError("Play")
        return play

    async def outcome(
        self,
        db,
        tenant_id,
        play_id,
        outcome,
        reason=None,
        *,
        device=None,
        actor: User | None = None,
    ):
        play = await self.owned(db, PlaySession, tenant_id, play_id, lock=True)
        if device and play.device_id != device.id:
            raise NotFoundError("Play")
        if play.status in {"activated", "refunded"}:
            if outcome == play.status or (outcome == "failed" and play.status == "refunded"):
                return play
            raise ConflictError("Play already has a final outcome")
        if actor is not None and play.status == "authorized":
            deadline = (
                play.execute_before.replace(tzinfo=UTC)
                if play.execute_before.tzinfo is None
                else play.execute_before
            )
            if deadline > datetime.now(UTC):
                raise ConflictError("Await the activation acknowledgement deadline")
        if actor is None and play.status == "unknown" and outcome == "failed":
            raise ConflictError("Uncertain play requires manager resolution")
        play.activation_outcome = "failed" if outcome == "refunded" else outcome
        if outcome in {"failed", "refunded"}:
            play.status = "unknown"
            refund = await LedgerService(commit=False).refund(
                db,
                tenant_id,
                play.transaction_id,
                uuid5(play.id, "refund"),
                None,
                reason or "Reader confirmed no activation",
            )
            play.refund_transaction_id = refund.refund_transaction_id
            play.status = "refunded"
        else:
            play.status = outcome
        play.outcome_at = datetime.now(UTC)
        play.resolution_reason = reason
        if actor:
            play.resolved_by = actor.id
            await AuditService().record(
                db,
                tenant_id,
                actor.id,
                "play.resolved",
                "play",
                str(play.id),
                {"outcome": play.status, "reason": reason},
            )
        await db.commit()
        return play

    async def customer_workspace(self, db, tenant_id, customer_id):
        customer = await self.owned(db, Customer, tenant_id, customer_id)
        cards = list(
            (
                await db.execute(
                    select(Card).where(Card.tenant_id == tenant_id, Card.customer_id == customer_id)
                )
            ).scalars()
        )
        wallets = list(
            (
                await db.execute(
                    select(Wallet).where(
                        Wallet.tenant_id == tenant_id, Wallet.customer_id == customer_id
                    )
                )
            ).scalars()
        )
        transactions = (
            await self.list_records(
                db,
                Transaction,
                tenant_id,
                1,
                100,
                filters=(Transaction.customer_id == customer_id,),
            )
        )["items"]
        plays = (
            await self.list_records(
                db,
                PlaySession,
                tenant_id,
                1,
                100,
                filters=(PlaySession.customer_id == customer_id,),
            )
        )["items"]
        receipts = (
            await self.list_records(
                db, Receipt, tenant_id, 1, 100, filters=(Receipt.customer_id == customer_id,)
            )
        )["items"]
        reserved = {
            str(wallet.id): await LedgerService()._active_hold_total(db, tenant_id, wallet.id)
            for wallet in wallets
        }
        limits = list(
            (
                await db.execute(
                    select(SpendingLimit).where(
                        SpendingLimit.tenant_id == tenant_id,
                        SpendingLimit.customer_id == customer_id,
                    )
                )
            ).scalars()
        )
        return CustomerWorkspace(
            customer=customer,
            cards=cards,
            wallets=wallets,
            transactions=transactions,
            plays=plays,
            receipts=receipts,
            reserved_minor=reserved,
            spending_limits=limits,
        )

    async def set_family(self, db, tenant_id, guardian_id, child_id):
        if guardian_id == child_id:
            raise ValidationError("Guardian and child must differ")
        for customer_id in sorted([guardian_id, child_id], key=str):
            await self.owned(db, Customer, tenant_id, customer_id, lock=True)
        # A v1 family is one guardian with children, without nested guardianship.
        existing = list(
            (
                await db.execute(
                    select(FamilyRelationship).where(FamilyRelationship.tenant_id == tenant_id)
                )
            ).scalars()
        )
        if any(row.child_id == guardian_id or row.guardian_id == child_id for row in existing):
            raise ConflictError("Nested family relationships are not supported")
        row = next((r for r in existing if r.child_id == child_id), None)
        if row and row.guardian_id != guardian_id:
            raise ConflictError("Child already has a guardian")
        if row is None:
            row = FamilyRelationship(
                tenant_id=tenant_id, guardian_id=guardian_id, child_id=child_id
            )
            db.add(row)
        await db.commit()
        return row

    async def set_limit(self, db, tenant_id, customer_id, payload):
        await self.owned(db, Customer, tenant_id, customer_id, lock=True)
        row = (
            await db.execute(
                select(SpendingLimit).where(
                    SpendingLimit.tenant_id == tenant_id,
                    SpendingLimit.customer_id == customer_id,
                    SpendingLimit.currency == payload.currency,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = SpendingLimit(
                tenant_id=tenant_id, customer_id=customer_id, **payload.model_dump()
            )
            db.add(row)
        else:
            row.daily_minor = payload.daily_minor
        await db.commit()
        return row
