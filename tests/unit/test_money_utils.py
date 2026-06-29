# tests/unit/test_money_utils.py

from decimal import Decimal

import pytest

from app.utils.money import assert_integer_amount, from_minor_units, to_minor_units

pytestmark = pytest.mark.asyncio


class TestMoneyUtils:
    async def test_to_minor_units(self):
        assert to_minor_units(Decimal("10.50")) == 1050

    async def test_from_minor_units(self):
        assert from_minor_units(1050) == Decimal("10.50")

    async def test_rejects_float_amount(self):
        with pytest.raises(ValueError, match="integer minor units"):
            assert_integer_amount(10.5)
