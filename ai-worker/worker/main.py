import asyncio

import asyncpg
import redis.asyncio as redis

from worker.core.config import settings
from worker.core.logging import configure_logging, get_logger
from worker.infrastructure.queue import NullJobQueue, assert_queue_protocol

logger = get_logger(__name__)


async def _verify_connectivity(pool: asyncpg.Pool, redis_client: redis.Redis) -> None:
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    await redis_client.ping()


async def run() -> None:
    configure_logging()
    assert_queue_protocol()

    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout_seconds,
    )
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )
    try:
        await _verify_connectivity(pool, redis_client)
        logger.info("worker.startup.connectivity_ok", service=settings.service_name)

        queue = NullJobQueue()
        _ = queue

        logger.info("worker.loop.stub_started", service=settings.service_name)
        while True:
            await asyncio.sleep(60)
            logger.info("worker.heartbeat.stub", service=settings.service_name)
    finally:
        await redis_client.aclose()
        await pool.close()
        logger.info("worker.shutdown.complete", service=settings.service_name)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
