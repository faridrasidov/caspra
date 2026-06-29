# app/engines/pricing.py

from decimal import Decimal
from uuid import UUID

from app.utils.money import to_minor_units


class PricingEngine:
    """Resolve product price, tax, and fees for a point-of-sale debit."""

    @staticmethod
    async def resolve_price(
        *,
        tenant_id: UUID,
        product_id: UUID,
        quantity: int = 1,
    ) -> tuple[int, str]:
        """Return (amount_minor, currency_code)."""
        _ = tenant_id, product_id, quantity
        return 0, "USD"

    @staticmethod
    def apply_tax(amount_minor: int, tax_rate: Decimal) -> int:
        tax_decimal = Decimal(amount_minor) / Decimal(100) * tax_rate
        return to_minor_units(tax_decimal, exponent=0)
