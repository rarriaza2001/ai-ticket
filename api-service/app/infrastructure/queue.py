from uuid import UUID

from shared_contracts import TicketEnqueueProtocol


class StubTicketEnqueue(TicketEnqueueProtocol):
    """No-op enqueue for Phase 1 wiring; replace with SQS/Redis producer in Phase 2."""

    async def enqueue_process_ticket(self, ticket_id: UUID, dedupe_key: str) -> None:
        _ = (ticket_id, dedupe_key)
        return None
