# migrations/env.py

import asyncio
import importlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models import Base

importlib.import_module("app.models")  # register all ORM tables on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure_context(*, connection=None, url: str | None = None) -> None:
    kwargs: dict = {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
        "transaction_per_migration": True,
    }

    if connection is not None:
        kwargs["connection"] = connection
        kwargs["render_as_batch"] = connection.dialect.name == "sqlite"
    else:
        kwargs["url"] = url
        kwargs["literal_binds"] = True
        kwargs["dialect_opts"] = {"paramstyle": "named"}
        kwargs["render_as_batch"] = "sqlite" in (url or "")

    context.configure(**kwargs)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    _configure_context(url=settings.sqlalchemy_database_uri)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Execute migrations inside a sync context via connection.run_sync()."""
    _configure_context(connection=connection)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an AsyncEngine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.sqlalchemy_database_uri

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
