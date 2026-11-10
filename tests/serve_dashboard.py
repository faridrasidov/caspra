"""Disposable loopback-only API for browser integration tests. Never uses .env DBs."""

import argparse
from contextlib import asynccontextmanager
import os
from pathlib import Path
import tempfile

os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "testing"
os.environ["REDIS_URL"] = "memory://"
os.environ["DEBUG"] = "false"
os.environ["SECRET_KEY"] = "isolated-browser-test-secret"
os.environ["DEVICE_SECRET_ENCRYPTION_KEY"] = "isolated-browser-device-key"

import uvicorn

from app.core.security import hash_password
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.models import Base
from app.models.identity.user import User
from app.models.tenant.organization import Organization
from app.services.operations import OperationsService


@asynccontextmanager
async def lifespan(app):
    with tempfile.TemporaryDirectory(prefix="caspra-e2e-") as folder:
        engine = create_engine(f"sqlite+aiosqlite:///{(Path(folder) / 'test.db').as_posix()}")
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with app.state.session_factory() as db:
            org = Organization(name="Sandbox arcade", slug="sandbox-pilot", default_currency="USD")
            db.add(org)
            await db.commit()
            roles = await OperationsService().roles(db)
            owner_role = next(role["id"] for role in roles if role["name"] == "owner")
            db.add(
                User(
                    tenant_id=org.id,
                    email="owner@pilot.test",
                    hashed_password=hash_password("browser-test-password"),
                    full_name="Pilot owner",
                    role_id=owner_role,
                )
            )
            await db.commit()
        yield
        await engine.dispose()


app = create_app()
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18005)
    arguments = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=arguments.port, log_level="warning")
