from typing import Protocol
from uuid import UUID

from shared_contracts import Ticket, TicketCreateRequest


class PostgresTicketRepositoryProtocol(Protocol):
    """Authoritative persistence boundary (Postgres only; implemented in Phase 2)."""

    async def insert_ticket(
        self,
        payload: TicketCreateRequest,
        *,
        idempotency_key: str | None,
    ) -> Ticket:
        ...

    async def get_by_id(self, ticket_id: UUID) -> Ticket | None:
        ...
