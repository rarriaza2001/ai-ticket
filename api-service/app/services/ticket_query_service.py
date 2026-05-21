from __future__ import annotations

import uuid

from app.core.errors import TicketNotFound
from app.db.models.draft_suggestion import DraftSuggestion
from app.db.models.routing_decision import RoutingDecision
from app.db.models.ticket import Ticket
from app.db.models.ticket_event import TicketEvent
from app.repositories.draft_suggestion_repository import DraftSuggestionRepository
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_embedding_repository import (
    SimilarTicketRow,
    TicketEmbeddingRepository,
)
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository


class TicketQueryService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        ticket_embedding_repository: TicketEmbeddingRepository,
        routing_decision_repository: RoutingDecisionRepository,
        ticket_event_repository: TicketEventRepository,
        draft_suggestion_repository: DraftSuggestionRepository,
    ) -> None:
        self._tickets = ticket_repository
        self._embeddings = ticket_embedding_repository
        self._routing = routing_decision_repository
        self._events = ticket_event_repository
        self._drafts = draft_suggestion_repository

    async def get_ticket(self, ticket_id: uuid.UUID) -> Ticket:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        return ticket

    async def get_ticket_status(self, ticket_id: uuid.UUID) -> str:
        status = await self._tickets.get_status(ticket_id)
        if status is None:
            raise TicketNotFound(ticket_id)
        return status

    async def list_tickets_by_status(
        self,
        status: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        return await self._tickets.list_by_status(status, limit=limit, offset=offset)

    async def is_ticket_searchable(self, ticket_id: uuid.UUID) -> bool:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)
        return await self._embeddings.has_active_embedding(ticket_id)

    async def get_latest_routing_decision(
        self, ticket_id: uuid.UUID
    ) -> RoutingDecision | None:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)
        return await self._routing.get_latest_for_ticket(ticket_id)

    async def get_latest_draft_suggestion(
        self, ticket_id: uuid.UUID
    ) -> DraftSuggestion | None:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)
        return await self._drafts.get_latest_for_ticket(ticket_id)

    async def get_audit_trail(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)
        return await self._events.list_for_ticket(ticket_id)

    async def search_similar_tickets(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        exclude_ticket_id: uuid.UUID | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> list[SimilarTicketRow]:
        return await self._embeddings.search_similar(
            query_embedding,
            limit=limit,
            exclude_ticket_id=exclude_ticket_id,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
