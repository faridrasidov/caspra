# app/api/public/endpoints/metadata.py

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.schemas.public import VersionOut

router = APIRouter(prefix="/metadata", tags=["public-metadata"])


@router.get("/version", response_model=VersionOut)
async def get_version() -> VersionOut:
    """Return the public API name and version. Open (no API key required)."""
    return VersionOut(name=settings.app_name, version=settings.app_version)


@router.get("/schema")
async def get_schema(request: Request) -> dict[str, Any]:
    """Return the OpenAPI schema filtered to public routes.

    Open (no API key required) so SDK generators can fetch the contract. Only
    paths under the public prefix are exposed; admin/device surfaces are hidden.
    """
    try:
        full_schema = request.app.openapi()
        prefix = settings.public_api_prefix
        public_paths = {
            path: item
            for path, item in full_schema.get("paths", {}).items()
            if path.startswith(prefix)
        }
        return {
            "openapi": full_schema.get("openapi"),
            "info": full_schema.get("info"),
            "paths": public_paths,
            "components": full_schema.get("components", {}),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build public schema: {e}",
        ) from e
