# app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.router import admin_router
from app.api.device.router import device_router
from app.api.docs import register_docs
from app.api.public.router import public_router
from app.api.v1.router import api_router
from app.core.config import settings, validate_runtime_settings
from app.core.http_errors import register_http_controls
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis
from app.db.session import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.debug)
    validate_runtime_settings(settings)
    engine = create_engine(settings.database_url, echo=settings.debug)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    await init_redis()
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    register_http_controls(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(admin_router, prefix=settings.admin_api_prefix)
    app.include_router(device_router, prefix=settings.device_api_prefix)
    app.include_router(public_router, prefix=settings.public_api_prefix)

    register_docs(app)
    return app


app = create_app()
