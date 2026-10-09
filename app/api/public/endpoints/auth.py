# app/api/public/endpoints/auth.py

from typing import Annotated

from fastapi import APIRouter, Depends

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
    return ApiKeyTestOut(valid=True, tenant_id=ctx.tenant_id, api_key_id=ctx.api_key_id)


@router.get("/scopes", response_model=ApiKeyScopesOut)
async def list_scopes(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
) -> ApiKeyScopesOut:
    """List the scopes granted to the presented API key."""
    return ApiKeyScopesOut(scopes=sorted(ctx.scopes))
