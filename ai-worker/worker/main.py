import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine

from worker.core.config import settings
from worker.core.logging import configure_logging, get_logger
from worker.infrastructure.connectivity import verify_connectivity
from worker.infrastructure.database import create_engine
from worker.infrastructure.redis import create_redis_client

logger = get_logger(__name__)


async def run() -> None:
    configure_logging()

    engine = create_engine(settings)
    redis_client = create_redis_client(settings)
    try:
        await verify_connectivity(engine, redis_client)
        logger.info("worker.startup.connectivity_ok", service=settings.service_name)

        logger.info("worker.loop.stub_started", service=settings.service_name)
        while True:
            await asyncio.sleep(60)
            logger.info("worker.heartbeat.stub", service=settings.service_name)
    finally:
        await redis_client.aclose()
        eng: AsyncEngine = engine
        await eng.dispose()
        logger.info("worker.shutdown.complete", service=settings.service_name)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
