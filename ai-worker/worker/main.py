import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine

from worker.core.config import get_settings, settings
from worker.core.logging import configure_logging, get_logger
from worker.db.session import create_session_factory
from worker.domain.enums import TicketStatus
from worker.infrastructure.connectivity import verify_connectivity
from worker.infrastructure.database import create_engine
from worker.infrastructure.redis import create_redis_client
from worker.repositories.ticket_repository import TicketRepository
from worker.services.ai_workflow_service import AiWorkflowService

logger = get_logger(__name__)


async def run() -> None:
    configure_logging()

    engine = create_engine(settings)
    redis_client = create_redis_client(settings)
    session_factory = create_session_factory(engine)
    try:
        settings.validate_openai_config()
        await verify_connectivity(engine, redis_client)
        logger.info("worker.startup.connectivity_ok", service=settings.service_name)

        logger.info(
            "worker.loop.started",
            service=settings.service_name,
            ai_provider=settings.ai_provider,
            poll_interval=settings.worker_poll_interval_seconds,
        )
        while True:
            async with session_factory() as session:
                tickets = TicketRepository(session)
                pending = await tickets.list_by_status(
                    TicketStatus.PENDING_EMBEDDING.value,
                    limit=settings.worker_batch_size,
                )
                for ticket in pending:
                    workflow = AiWorkflowService(session, settings, redis_client=redis_client)
                    try:
                        await workflow.process_ticket(ticket.id)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception(
                            "ai.workflow.unhandled",
                            ticket_id=str(ticket.id),
                        )
            await asyncio.sleep(settings.worker_poll_interval_seconds)
    finally:
        await redis_client.aclose()
        eng: AsyncEngine = engine
        await eng.dispose()
        logger.info("worker.shutdown.complete", service=settings.service_name)


def main() -> None:
    get_settings.cache_clear()
    asyncio.run(run())


if __name__ == "__main__":
    main()
