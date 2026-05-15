"""Startup dependency connectivity checks (no business logic)."""

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def verify_connectivity(engine: AsyncEngine, redis_client: redis.Redis) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await redis_client.ping()
