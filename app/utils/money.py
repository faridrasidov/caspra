# app/utils/money.py

from decimal import ROUND_HALF_UP, Decimal


def to_minor_units(amount: Decimal, exponent: int = 2) -> int:
    """Convert a decimal amount to integer minor units (e.g. cents)."""
    multiplier = Decimal(10) ** exponent
    minor = (amount * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def from_minor_units(amount_minor: int, exponent: int = 2) -> Decimal:
    """Convert integer minor units back to a decimal amount."""
    divisor = Decimal(10) ** exponent
    return Decimal(amount_minor) / divisor


def assert_integer_amount(amount: int | float) -> int:
    """Reject float amounts — money must be stored as integer minor units."""
    if isinstance(amount, float):
        raise ValueError("Money amounts must be integer minor units, not float")
    return int(amount)
