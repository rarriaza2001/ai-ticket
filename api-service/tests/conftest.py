from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.embedding import EMBEDDING_DIMENSION
from app.db.session import create_session_factory
from app.main import create_app

DEFAULT_DATABASE_URL = "postgresql://ticket:ticket@localhost:5433/tickets"


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


@pytest.fixture(scope="session")
def database_url() -> str:
    return _database_url()


@pytest.fixture(scope="session", autouse=True)
def run_migrations(database_url: str) -> Generator[None, None, None]:
    os.environ["DATABASE_URL"] = database_url
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(_async_url(database_url), pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    yield create_session_factory(engine)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[None, None]:
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE draft_suggestions, ticket_events, routing_decisions, "
                "ticket_embeddings, tickets RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    from unittest.mock import AsyncMock, MagicMock

    app = create_app()
    app.state.session_factory = session_factory
    store: dict[str, str] = {}
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    async def _get(key: str):
        return store.get(key)

    async def _set(key: str, value: str, ex: int | None = None):
        store[key] = value
        return True

    async def _delete(*keys: str):
        for key in keys:
            store.pop(key, None)
        return len(keys)

    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.set = AsyncMock(side_effect=_set)
    mock_redis.delete = AsyncMock(side_effect=_delete)
    mock_redis._store = store
    app.state.redis = mock_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fake_embedding() -> list[float]:
    """Deterministic unit vector slice for tests (no AI)."""
    vec = [0.0] * EMBEDDING_DIMENSION
    vec[0] = 1.0
    return vec


@pytest.fixture
def fake_embedding_alt() -> list[float]:
    vec = [0.0] * EMBEDDING_DIMENSION
    vec[1] = 1.0
    return vec


@pytest.fixture
def settings_override(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()
