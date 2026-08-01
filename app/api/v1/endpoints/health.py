# app/api/v1/endpoints/health.py

from time import perf_counter

from fastapi import APIRouter, Request, Response, status
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.metrics import increment_metric, observe_metric, render_metrics
from app.core.redis import get_redis_optional
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check() -> HealthOut:
    """Return service health and version."""
    return HealthOut(status="ok", version=settings.app_version)


@router.get("/health/live", response_model=HealthOut)
async def liveness() -> HealthOut:
    return HealthOut(status="ok", version=settings.app_version)


@router.get("/health/ready", response_model=HealthOut)
async def readiness(request: Request, response: Response) -> HealthOut:
    components: dict[str, str] = {}
    db_started = perf_counter()
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        components["database"] = "ok"
    except (AttributeError, OSError, SQLAlchemyError):
        components["database"] = "unavailable"
        increment_metric("database_failures_total")
    finally:
        observe_metric("database_latency_seconds", perf_counter() - db_started)

    redis_client = get_redis_optional()
    if redis_client is None:
        components["redis"] = "not_configured" if settings.testing else "unavailable"
    else:
        try:
            await redis_client.ping()
            components["redis"] = "ok"
        except (OSError, RedisError):
            components["redis"] = "unavailable"
            increment_metric("redis_failures_total")

    required = {"database": "ok"}
    if settings.environment == "production":
        required["redis"] = "ok"
    ready = all(components.get(name) == expected for name, expected in required.items())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(
        status="ok" if ready else "not_ready",
        version=settings.app_version,
        components=components,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics():
    return render_metrics()
