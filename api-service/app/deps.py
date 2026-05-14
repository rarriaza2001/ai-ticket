from typing import Annotated

import asyncpg
import redis.asyncio as redis
from fastapi import Depends, Request


def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


def get_redis_client(request: Request) -> redis.Redis:
    return request.app.state.redis


DbPool = Annotated[asyncpg.Pool, Depends(get_db_pool)]
RedisClient = Annotated[redis.Redis, Depends(get_redis_client)]
