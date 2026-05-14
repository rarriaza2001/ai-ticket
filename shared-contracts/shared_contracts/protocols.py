from typing import Protocol
from uuid import UUID

from shared_contracts.jobs import TicketProcessJob


class JobQueue(Protocol):
    """Inbound job consumption boundary (SQS, Redis Stream, etc. in Phase 2)."""

    async def dequeue(self) -> TicketProcessJob | None:
        """Return next job or None if queue is empty / not configured."""
        ...

    async def ack(self, job_id: UUID) -> None:
        """Acknowledge successful processing."""
        ...


class TicketEnqueueProtocol(Protocol):
    """API-side enqueue boundary for worker jobs."""

    async def enqueue_process_ticket(self, ticket_id: UUID, dedupe_key: str) -> None:
        ...
