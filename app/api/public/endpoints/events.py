# app/api/public/endpoints/events.py

import asyncio
from collections.abc import AsyncGenerator
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import ApiKeyContext, get_api_key, rate_limit_public

router = APIRouter(
    prefix="/events",
    tags=["public-events"],
    dependencies=[Depends(rate_limit_public)],
)

# Number of heartbeats emitted before the demo stream closes. A real
# implementation would stream indefinitely and fan out tenant events from a
# Redis pub/sub channel (TODO); the bounded loop keeps the endpoint responsive
# and testable without a live broker.
_HEARTBEAT_COUNT = 3
_HEARTBEAT_INTERVAL_S = 0.0


async def _event_generator(ctx: ApiKeyContext) -> AsyncGenerator[str]:
    yield f"event: connected\ndata: {json.dumps({'tenant_id': str(ctx.tenant_id)})}\n\n"
    for seq in range(_HEARTBEAT_COUNT):
        yield f"event: heartbeat\ndata: {json.dumps({'seq': seq})}\n\n"
        if _HEARTBEAT_INTERVAL_S:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)


@router.get("/stream")
async def stream_events(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key)],
) -> StreamingResponse:
    """Server-Sent Events stream authenticated by API key.

    TODO: replace the heartbeat demo with real per-tenant event fan-out backed
    by Redis pub/sub so events posted anywhere in the platform reach subscribers.
    """
    return StreamingResponse(_event_generator(ctx), media_type="text/event-stream")
