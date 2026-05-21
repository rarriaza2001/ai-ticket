from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
API_SERVICE = ROOT / "api-service"
if str(API_SERVICE) not in sys.path:
    sys.path.insert(0, str(API_SERVICE))

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
    os.chdir(API_SERVICE)
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def force_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(_async_url(database_url), pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    from worker.db.session import create_session_factory

    yield create_session_factory(engine)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
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


@pytest.fixture
def mock_provider():
    from worker.providers.mock_provider import MockAiProvider

    return MockAiProvider()


@pytest.fixture
def worker_settings(database_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    from worker.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()
