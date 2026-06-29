# app/api/public/endpoints/auth.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import ApiKeyContext, get_api_key, rate_limit_public
from app.schemas.public import ApiKeyScopesOut, ApiKeyTestOut

router = APIRouter(
    prefix="/auth",
    tags=["public-auth"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("/test", response_model=ApiKeyTestOut)
async def test_api_key(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
) -> ApiKeyTestOut:
    """Validate the presented API key and echo its tenant binding."""
    try:
        return ApiKeyTestOut(valid=True, tenant_id=ctx.tenant_id, api_key_id=ctx.api_key_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate API key: {e}",
        ) from e


@router.get("/scopes", response_model=ApiKeyScopesOut)
async def list_scopes(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
) -> ApiKeyScopesOut:
    """List the scopes granted to the presented API key."""
    try:
        return ApiKeyScopesOut(scopes=sorted(ctx.scopes))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scopes: {e}",
        ) from e
