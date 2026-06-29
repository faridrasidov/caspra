# app/db/session.py

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.decl_api import declared_attr


class Base(DeclarativeBase):
    """SQLAlchemy declarative base with Postgres naming conventions."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"


def create_engine(database_url: str, *, echo: bool = False):
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session
