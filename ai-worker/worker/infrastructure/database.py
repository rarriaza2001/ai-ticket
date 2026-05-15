"""SQLAlchemy async engine factory for the worker."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from worker.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_async_url,
        pool_pre_ping=True,
    )
