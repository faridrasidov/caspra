# tests/unit/test_rate_limit.py

import pytest

from app.core import rate_limit
from app.core.config import settings
from app.core.domain_errors import TooManyRequestsError

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def local_limiter(monkeypatch):
    """Force the in-memory fallback with a clean store and a fake clock."""
    clock = {"now": 1_000.0}
    monkeypatch.setattr(rate_limit, "get_redis_optional", lambda: None)
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(rate_limit, "_local_attempts", rate_limit.defaultdict(rate_limit.deque))
    return clock


async def test_blocks_after_limit_within_window():
    for _ in range(settings.login_rate_limit_per_minute):
        await rate_limit.check_login_rate_limit("10.0.0.1", "a@example.test")
    with pytest.raises(TooManyRequestsError, match="Too many login attempts"):
        await rate_limit.check_login_rate_limit("10.0.0.1", "A@example.test")


async def test_window_expiry_allows_new_attempts(local_limiter):
    for _ in range(settings.login_rate_limit_per_minute):
        await rate_limit.check_login_rate_limit("10.0.0.1", "a@example.test")
    local_limiter["now"] += 61
    await rate_limit.check_login_rate_limit("10.0.0.1", "a@example.test")


async def test_clear_resets_the_counter():
    for _ in range(settings.login_rate_limit_per_minute):
        key = await rate_limit.check_login_rate_limit("10.0.0.1", "a@example.test")
    await rate_limit.clear_login_rate_limit(key)
    await rate_limit.check_login_rate_limit("10.0.0.1", "a@example.test")


async def test_expired_identities_are_swept(local_limiter, monkeypatch):
    monkeypatch.setattr(rate_limit, "_LOCAL_SWEEP_THRESHOLD", 5)
    for n in range(6):
        await rate_limit.check_login_rate_limit("10.0.0.1", f"user{n}@example.test")
    assert len(rate_limit._local_attempts) == 6

    local_limiter["now"] += 61
    await rate_limit.check_login_rate_limit("10.0.0.2", "fresh@example.test")

    assert len(rate_limit._local_attempts) == 1


async def test_sweep_keeps_identities_still_in_window(local_limiter, monkeypatch):
    monkeypatch.setattr(rate_limit, "_LOCAL_SWEEP_THRESHOLD", 2)
    await rate_limit.check_login_rate_limit("10.0.0.1", "old@example.test")
    local_limiter["now"] += 61
    await rate_limit.check_login_rate_limit("10.0.0.1", "recent1@example.test")
    await rate_limit.check_login_rate_limit("10.0.0.1", "recent2@example.test")
    await rate_limit.check_login_rate_limit("10.0.0.1", "recent3@example.test")

    assert len(rate_limit._local_attempts) == 3
