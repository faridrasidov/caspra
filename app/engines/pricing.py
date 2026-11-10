from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.domain_errors import NotFoundError, ValidationError
from app.models.catalog.arcade import PricingSchedule
from app.models.catalog.product import Product


class PricingEngine:
    async def resolve_price(self, db, *, tenant_id, product_id, quantity=1):
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValidationError("Quantity must be a positive integer")
        product = (
            await db.execute(
                select(Product).where(
                    Product.tenant_id == tenant_id,
                    Product.id == product_id,
                    Product.active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if product is None:
            raise NotFoundError("Product")
        return product.price_minor * quantity, product.currency

    async def resolve_machine_price(self, db, machine, now, timezone):
        local = now.astimezone(ZoneInfo(timezone))
        minute = local.hour * 60 + local.minute
        schedule = (
            await db.execute(
                select(PricingSchedule).where(
                    PricingSchedule.tenant_id == machine.tenant_id,
                    PricingSchedule.machine_id == machine.id,
                    PricingSchedule.active.is_(True),
                    PricingSchedule.weekday == local.weekday(),
                    PricingSchedule.start_minute <= minute,
                    PricingSchedule.end_minute > minute,
                )
            )
        ).scalar_one_or_none()
        return {
            "machine_name": machine.name,
            "location_id": str(machine.location_id) if machine.location_id else None,
            "revision": machine.price_revision,
            "amount_minor": schedule.price_minor if schedule else machine.price_minor,
            "currency": machine.currency,
            "schedule_id": str(schedule.id) if schedule else None,
            "timezone": timezone,
        }

    @staticmethod
    def apply_tax(amount_minor: int, tax_rate: Decimal) -> int:
        if tax_rate < 0:
            raise ValidationError("Tax rate cannot be negative")
        return int(
            (Decimal(amount_minor) * tax_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
