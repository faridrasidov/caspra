from collections import defaultdict, deque
from contextlib import suppress
import hashlib
import time

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.domain_errors import ServiceUnavailableError, TooManyRequestsError
from app.core.redis import get_redis_optional

_local_attempts: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_SECONDS = 60
# Non-production fallback only. Past this many tracked identities, expired
# entries are swept so one-off attempts cannot grow the dict without bound.
_LOCAL_SWEEP_THRESHOLD = 10_000


def _login_key(client_ip: str, email: str) -> str:
    identity = hashlib.sha256(f"{client_ip}:{email.lower()}".encode()).hexdigest()
    return f"caspra:login-attempts:{identity}"


async def check_login_rate_limit(client_ip: str, email: str) -> str:
    key = _login_key(client_ip, email)
    redis_client = get_redis_optional()
    if redis_client is not None:
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, _WINDOW_SECONDS)
            if count > settings.login_rate_limit_per_minute:
                raise TooManyRequestsError("Too many login attempts; try again later")
            return key
        except TooManyRequestsError:
            raise
        except RedisError as exc:
            if settings.environment == "production":
                raise ServiceUnavailableError("Login protection is unavailable") from exc

    if settings.environment == "production":
        raise ServiceUnavailableError("Login protection is unavailable")
    now = time.monotonic()
    if len(_local_attempts) > _LOCAL_SWEEP_THRESHOLD:
        _sweep_expired(now)
    attempts = _local_attempts[key]
    while attempts and attempts[0] <= now - _WINDOW_SECONDS:
        attempts.popleft()
    attempts.append(now)
    if len(attempts) > settings.login_rate_limit_per_minute:
        raise TooManyRequestsError("Too many login attempts; try again later")
    return key


def _sweep_expired(now: float) -> None:
    cutoff = now - _WINDOW_SECONDS
    for stale in [k for k, attempts in _local_attempts.items() if attempts[-1] <= cutoff]:
        del _local_attempts[stale]


async def clear_login_rate_limit(key: str) -> None:
    redis_client = get_redis_optional()
    if redis_client is not None:
        with suppress(RedisError):
            await redis_client.delete(key)
    _local_attempts.pop(key, None)
