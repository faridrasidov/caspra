# app/api/v1/endpoints/health.py

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check() -> HealthOut:
    """Return service health and version."""
    return HealthOut(status="ok", version=settings.app_version)
