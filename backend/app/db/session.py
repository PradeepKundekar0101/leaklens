"""Async SQLAlchemy engine and sessions (psycopg 3)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _connect_args() -> dict:
    settings = get_settings()
    # DO's PgBouncer in transaction mode cannot handle server-side prepared statements.
    if settings.db_pool_mode == "transaction":
        return {"prepare_threshold": None}
    return {}


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10, connect_args=_connect_args()
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request."""
    async with get_sessionmaker()() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@asynccontextmanager
async def readonly_session() -> AsyncIterator[AsyncSession]:
    """A session whose transaction is READ ONLY at the database level. Used by every agent tool."""
    async with get_sessionmaker()() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield session
        finally:
            await session.rollback()
