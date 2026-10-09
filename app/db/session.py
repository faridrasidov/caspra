# app/db/session.py

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Matches the names already used in the models and migrations, so constraints
# that are not named explicitly still get stable, predictable names. Check
# constraints are left out: a ``%(constraint_name)s`` convention would rewrap
# the existing explicit ``ck_*`` names.
NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
}


class Base(DeclarativeBase):
    """SQLAlchemy declarative base with Postgres naming conventions.

    Every model must set ``__tablename__`` explicitly.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(database_url: str, *, echo: bool = False):
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session
