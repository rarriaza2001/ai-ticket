from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.draft_suggestion_repository import DraftSuggestionRepository
from app.repositories.health_repository import HealthRepository
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.readiness_service import ReadinessService
from app.services.routing_persistence_service import RoutingPersistenceService
from app.services.ticket_intake_service import TicketIntakeService
from app.services.ticket_query_service import TicketQueryService


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_redis_client(request: Request) -> redis.Redis:
    return request.app.state.redis


def get_ticket_repository(session: AsyncSession = Depends(get_db_session)) -> TicketRepository:
    return TicketRepository(session)


def get_ticket_embedding_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TicketEmbeddingRepository:
    return TicketEmbeddingRepository(session)


def get_routing_decision_repository(
    session: AsyncSession = Depends(get_db_session),
) -> RoutingDecisionRepository:
    return RoutingDecisionRepository(session)


def get_ticket_event_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TicketEventRepository:
    return TicketEventRepository(session)


def get_draft_suggestion_repository(
    session: AsyncSession = Depends(get_db_session),
) -> DraftSuggestionRepository:
    return DraftSuggestionRepository(session)


def get_ticket_intake_service(
    tickets: TicketRepository = Depends(get_ticket_repository),
    events: TicketEventRepository = Depends(get_ticket_event_repository),
) -> TicketIntakeService:
    return TicketIntakeService(tickets, events)


def get_ticket_query_service(
    tickets: TicketRepository = Depends(get_ticket_repository),
    embeddings: TicketEmbeddingRepository = Depends(get_ticket_embedding_repository),
    routing: RoutingDecisionRepository = Depends(get_routing_decision_repository),
    events: TicketEventRepository = Depends(get_ticket_event_repository),
    drafts: DraftSuggestionRepository = Depends(get_draft_suggestion_repository),
) -> TicketQueryService:
    return TicketQueryService(tickets, embeddings, routing, events, drafts)


def get_embedding_persistence_service(
    tickets: TicketRepository = Depends(get_ticket_repository),
    embeddings: TicketEmbeddingRepository = Depends(get_ticket_embedding_repository),
    events: TicketEventRepository = Depends(get_ticket_event_repository),
) -> EmbeddingPersistenceService:
    return EmbeddingPersistenceService(tickets, embeddings, events)


def get_routing_persistence_service(
    tickets: TicketRepository = Depends(get_ticket_repository),
    routing: RoutingDecisionRepository = Depends(get_routing_decision_repository),
    events: TicketEventRepository = Depends(get_ticket_event_repository),
) -> RoutingPersistenceService:
    return RoutingPersistenceService(tickets, routing, events)


def get_readiness_service(
    session: AsyncSession = Depends(get_db_session),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> ReadinessService:
    return ReadinessService(HealthRepository(session), redis_client)


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[redis.Redis, Depends(get_redis_client)]
ReadinessSvc = Annotated[ReadinessService, Depends(get_readiness_service)]
TicketIntakeSvc = Annotated[TicketIntakeService, Depends(get_ticket_intake_service)]
TicketQuerySvc = Annotated[TicketQueryService, Depends(get_ticket_query_service)]
EmbeddingPersistenceSvc = Annotated[
    EmbeddingPersistenceService, Depends(get_embedding_persistence_service)
]
RoutingPersistenceSvc = Annotated[
    RoutingPersistenceService, Depends(get_routing_persistence_service)
]
