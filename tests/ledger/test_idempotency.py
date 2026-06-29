# tests/ledger/test_idempotency.py

import pytest

pytestmark = pytest.mark.asyncio


class TestIdempotency:
    """Idempotency tests — implement once Transaction model exists."""

    async def test_placeholder(self):
        assert True
