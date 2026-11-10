from datetime import UTC, datetime
from uuid import uuid4, uuid5

from sqlalchemy import func, select

from app.core.domain_errors import ConflictError, ForbiddenError, ValidationError
from app.models.ledger.wallet import Customer, Wallet
from app.models.tenant.organization import Location
from app.models.tenant.venue import CashierShift, CashMovement, Receipt, TopupPackage
from app.schemas.wallet import WalletTopupRequest
from app.services.arcade import ArcadeService
from app.services.audit import AuditService
from app.services.ledger import LedgerService
from app.utils.idempotency import canonical_request_hash


class VenueService(ArcadeService):
    async def open_shift(self, db, actor, payload):
        # Serialize openings by cashier, then enforce terminal uniqueness in the DB.
        await db.refresh(actor, with_for_update=True)
        if payload.location_id:
            await self.owned(db, Location, actor.tenant_id, payload.location_id)
        existing = select(CashierShift.id).where(
            CashierShift.tenant_id == actor.tenant_id,
            CashierShift.closed_at.is_(None),
            (CashierShift.cashier_id == actor.id) | (CashierShift.terminal == payload.terminal),
        )
        if (await db.execute(existing)).first():
            raise ConflictError("Cashier or terminal already has an open shift")
        row = CashierShift(tenant_id=actor.tenant_id, cashier_id=actor.id, **payload.model_dump())
        db.add(row)
        await db.commit()
        return row

    async def close_shift(self, db, actor, shift_id, payload):
        row = await self.owned(db, CashierShift, actor.tenant_id, shift_id, lock=True)
        if row.cashier_id != actor.id:
            raise ForbiddenError("Close your own shift")
        if row.closed_at:
            if row.counted_minor != payload.counted_minor:
                raise ConflictError("Shift already closed with another count")
            return row
        receipts = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(Receipt.paid_minor), 0)).where(
                        Receipt.tenant_id == actor.tenant_id,
                        Receipt.shift_id == row.id,
                        Receipt.tender == "cash",
                    )
                )
            ).scalar_one()
        )
        movements = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(CashMovement.amount_minor), 0)).where(
                        CashMovement.tenant_id == actor.tenant_id, CashMovement.shift_id == row.id
                    )
                )
            ).scalar_one()
        )
        row.expected_minor = row.opening_minor + receipts + movements
        row.counted_minor = payload.counted_minor
        row.variance_minor = payload.counted_minor - row.expected_minor
        row.closed_at = datetime.now(UTC)
        await db.commit()
        return row

    async def review_shift(self, db, actor, shift_id, payload):
        row = await self.owned(db, CashierShift, actor.tenant_id, shift_id, lock=True)
        if row.closed_at is None:
            raise ConflictError("Close shift before variance review")
        row.reviewed_by = actor.id
        row.review_reason = payload.reason
        await AuditService().record(
            db,
            actor.tenant_id,
            actor.id,
            "shift.reviewed",
            "shift",
            str(row.id),
            {"reason": payload.reason, "variance_minor": row.variance_minor},
        )
        await db.commit()
        return row

    async def cash_movement(self, db, actor, shift_id, payload):
        shift = await self.owned(db, CashierShift, actor.tenant_id, shift_id, lock=True)
        request_hash = canonical_request_hash(
            "cash.movement", shift_id=shift_id, **payload.model_dump(exclude={"idempotency_key"})
        )
        existing = (
            await db.execute(
                select(CashMovement).where(
                    CashMovement.tenant_id == actor.tenant_id,
                    CashMovement.idempotency_key == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Idempotency key was reused", code="idempotency_conflict")
            return existing
        if shift.closed_at is not None or payload.amount_minor == 0:
            raise ValidationError("Use an open shift and a nonzero movement")
        row = CashMovement(
            tenant_id=actor.tenant_id,
            actor_id=actor.id,
            shift_id=shift.id,
            request_hash=request_hash,
            **payload.model_dump(),
        )
        db.add(row)
        await db.commit()
        return row

    async def create_package(self, db, tenant_id, payload):
        row = TopupPackage(tenant_id=tenant_id, **payload.model_dump())
        db.add(row)
        await db.commit()
        return row

    async def disable_package(self, db, tenant_id, package_id):
        row = await self.owned(db, TopupPackage, tenant_id, package_id, lock=True)
        row.active = False
        await db.commit()

    async def funding_wallet(self, db, tenant_id, customer_id, currency, kind):
        row = (
            await db.execute(
                select(Wallet).where(
                    Wallet.tenant_id == tenant_id,
                    Wallet.customer_id == customer_id,
                    Wallet.currency == currency,
                    Wallet.type == kind,
                    Wallet.status != "closed",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = Wallet(tenant_id=tenant_id, customer_id=customer_id, currency=currency, type=kind)
            db.add(row)
            await db.flush()
        return row

    async def fund_customer(
        self,
        db,
        tenant_id,
        customer_id,
        *,
        currency,
        amount,
        bonus,
        key,
        actor_id=None,
        shift_id=None,
        tender="cash",
        package_snapshot=None,
        request_hash=None,
    ):
        customer = await self.owned(db, Customer, tenant_id, customer_id, lock=True)
        if customer.status != "active":
            raise ValidationError("Customer is not active")
        existing = (
            await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == tenant_id, Receipt.idempotency_key == key
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Idempotency key was reused", code="idempotency_conflict")
            return existing
        transactions = []
        buckets = {}
        for kind, value in (("credit", amount), ("bonus", bonus)):
            if value:
                buckets[kind] = await self.funding_wallet(
                    db, tenant_id, customer_id, currency, kind
                )
        for wallet in sorted(buckets.values(), key=lambda w: str(w.id)):
            await LedgerService(commit=False)._get_wallet_locked(db, tenant_id, wallet.id)
        for kind, value in (("credit", amount), ("bonus", bonus)):
            if value:
                wallet = buckets[kind]
                txn = await LedgerService(commit=False).topup(
                    db,
                    tenant_id,
                    wallet.id,
                    WalletTopupRequest(
                        amount_minor=value,
                        currency=currency,
                        idempotency_key=uuid5(key, kind),
                        description=f"{tender} top-up",
                    ),
                )
                transactions.append(str(txn.id))
        row = Receipt(
            tenant_id=tenant_id,
            number=f"C-{uuid4().hex.upper()}",
            shift_id=shift_id,
            actor_id=actor_id,
            customer_id=customer_id,
            idempotency_key=key,
            request_hash=request_hash,
            paid_minor=amount,
            bonus_minor=bonus,
            currency=currency,
            tender=tender,
            package_snapshot=package_snapshot,
            transaction_ids=transactions,
        )
        db.add(row)
        await db.flush()
        return row

    async def cash_topup(self, db, actor, payload):
        shift = await self.owned(db, CashierShift, actor.tenant_id, payload.shift_id, lock=True)
        if shift.cashier_id != actor.id:
            raise ForbiddenError("Use your own shift")
        request_hash = canonical_request_hash(
            "cash.topup", **payload.model_dump(exclude={"idempotency_key"})
        )
        existing = (
            await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == actor.tenant_id,
                    Receipt.idempotency_key == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Idempotency key was reused", code="idempotency_conflict")
            return existing
        if shift.closed_at is not None or shift.currency != payload.currency:
            raise ValidationError("Use an open shift with matching currency")
        bonus = 0
        snapshot = None
        if payload.package_id:
            package = await self.owned(
                db, TopupPackage, actor.tenant_id, payload.package_id, lock=True
            )
            if (
                not package.active
                or package.currency != payload.currency
                or package.paid_minor != payload.amount_minor
            ):
                raise ValidationError("Package does not match payment")
            bonus = package.bonus_minor
            snapshot = {
                "id": str(package.id),
                "name": package.name,
                "paid_minor": package.paid_minor,
                "bonus_minor": bonus,
            }
        receipt = await self.fund_customer(
            db,
            actor.tenant_id,
            payload.customer_id,
            currency=payload.currency,
            amount=payload.amount_minor,
            bonus=bonus,
            key=payload.idempotency_key,
            actor_id=actor.id,
            shift_id=shift.id,
            request_hash=request_hash,
            package_snapshot=snapshot,
        )
        await db.commit()
        return receipt
