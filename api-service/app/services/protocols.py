from typing import Protocol
from uuid import UUID

from shared_contracts import (
    RoutingDecision,
    SimilarTicketSnapshot,
    Ticket,
    TicketCreateRequest,
    TicketSuggestion,
)


class TicketServiceProtocol(Protocol):
    """Application service for ticket lifecycle orchestration (Phase 2)."""

    async def create_ticket(
        self,
        payload: TicketCreateRequest,
        *,
        idempotency_key: str | None,
    ) -> Ticket:
        ...

    async def get_ticket(self, ticket_id: UUID) -> Ticket | None:
        ...

    async def reprocess(self, ticket_id: UUID) -> Ticket:
        ...


class RoutingQueryProtocol(Protocol):
    async def get_routing(self, ticket_id: UUID) -> RoutingDecision | None:
        ...

    async def get_suggestion(self, ticket_id: UUID) -> TicketSuggestion | None:
        ...

    async def get_similar(self, ticket_id: UUID) -> SimilarTicketSnapshot | None:
        ...
