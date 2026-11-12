"""Async engine/sessionmaker factory and schema bootstrap."""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.repositories.sqlalchemy_repos.orm import Base


def build_sessionmaker(database_url: str) -> async_sessionmaker:
    """Session-per-repository-call: each repository method opens a short
    transaction (begin/commit or rollback). expire_on_commit=False keeps
    detached instances readable after the session closes."""
    engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_schema(sessionmaker: async_sessionmaker) -> None:
    engine = sessionmaker.kw["bind"]
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose(sessionmaker: async_sessionmaker) -> None:
    engine = sessionmaker.kw["bind"]
    await engine.dispose()
