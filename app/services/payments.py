from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.domain_errors import (
    ConflictError,
    ForbiddenError,
    ServiceUnavailableError,
    ValidationError,
)
from app.models.identity.customer import PaymentCheckout
from app.models.ledger.wallet import Customer
from app.models.tenant.organization import Organization
from app.models.tenant.venue import TopupPackage
from app.schemas.arcade import CheckoutOut
from app.services.venue import VenueService
from app.utils.idempotency import canonical_request_hash


class PaymentProvider(Protocol):
    async def create_checkout(self, checkout: PaymentCheckout) -> str | None: ...
    async def validate_notification(self, body: bytes, headers: dict) -> dict: ...
    async def verify_payment(self, checkout: PaymentCheckout, notification: dict) -> bool: ...


class SandboxPaymentProvider:
    async def create_checkout(self, checkout):
        return None

    async def validate_notification(self, body, headers):
        raise ServiceUnavailableError("Sandbox has no external payment notifications")

    async def verify_payment(self, checkout, notification):
        return notification == {
            "reference": checkout.provider_reference,
            "amount_minor": checkout.amount_minor,
            "currency": checkout.currency,
            "status": "success",
        }


class PaymentService(VenueService):
    async def adapter(self, db, identity):
        if settings.environment == "production" or settings.payment_provider != "sandbox":
            raise ServiceUnavailableError("Online top-ups are unavailable")
        org = await db.get(Organization, identity.tenant_id)
        if not settings.testing and not org.slug.startswith("sandbox-"):
            raise ForbiddenError("Sandbox payments require a sandbox venue")
        return SandboxPaymentProvider()

    async def create(self, db, identity, payload):
        provider = await self.adapter(db, identity)
        await self.owned(db, Customer, identity.tenant_id, identity.customer_id, lock=True)
        request_hash = canonical_request_hash(
            "checkout",
            customer_id=identity.customer_id,
            **payload.model_dump(exclude={"idempotency_key"}),
        )
        row = (
            await db.execute(
                select(PaymentCheckout).where(
                    PaymentCheckout.tenant_id == identity.tenant_id,
                    PaymentCheckout.idempotency_key == payload.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if row:
            if row.request_hash != request_hash:
                raise ConflictError("Idempotency key was reused", code="idempotency_conflict")
        else:
            bonus, snapshot = 0, None
            if payload.package_id:
                package = await self.owned(db, TopupPackage, identity.tenant_id, payload.package_id)
                if (
                    not package.active
                    or package.currency != payload.currency
                    or package.paid_minor != payload.amount_minor
                ):
                    raise ValidationError("Package does not match checkout")
                bonus = package.bonus_minor
                snapshot = {
                    "id": str(package.id),
                    "name": package.name,
                    "paid_minor": package.paid_minor,
                    "bonus_minor": bonus,
                }
            row = PaymentCheckout(
                tenant_id=identity.tenant_id,
                customer_id=identity.customer_id,
                idempotency_key=payload.idempotency_key,
                request_hash=request_hash,
                amount_minor=payload.amount_minor,
                currency=payload.currency,
                bonus_minor=bonus,
                package_snapshot=snapshot,
                provider="sandbox",
                provider_reference=f"sandbox-{uuid4().hex}",
            )
            db.add(row)
            await db.flush()
            await provider.create_checkout(row)
            await db.commit()
        return CheckoutOut(session_id=row.id, status=row.status, provider=row.provider)

    async def simulate(self, db, identity, checkout_id):
        provider = await self.adapter(db, identity)
        row = await self.owned(db, PaymentCheckout, identity.tenant_id, checkout_id, lock=True)
        if row.customer_id != identity.customer_id:
            raise ForbiddenError("Checkout belongs to another customer")
        if row.status == "confirmed":
            return CheckoutOut(session_id=row.id, status=row.status, provider=row.provider)
        created = (
            row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        )
        if datetime.now(UTC) - created > timedelta(minutes=30):
            raise ConflictError("Checkout expired")
        notification = {
            "reference": row.provider_reference,
            "amount_minor": row.amount_minor,
            "currency": row.currency,
            "status": "success",
        }
        if not await provider.verify_payment(row, notification):
            raise ForbiddenError("Payment could not be verified")
        receipt = await self.fund_customer(
            db,
            row.tenant_id,
            row.customer_id,
            currency=row.currency,
            amount=row.amount_minor,
            bonus=row.bonus_minor,
            key=row.idempotency_key,
            tender="sandbox",
            package_snapshot=row.package_snapshot,
            request_hash=row.request_hash,
        )
        row.receipt_id = receipt.id
        row.status = "confirmed"
        await db.commit()
        return CheckoutOut(session_id=row.id, status=row.status, provider=row.provider)
