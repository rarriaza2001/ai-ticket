from uuid import UUID

from shared_contracts.jobs import TicketProcessJob
from shared_contracts.protocols import JobQueue


class NullJobQueue:
    """Phase 1 stand-in; replace with durable consumer (SQS, Redis Stream, etc.)."""

    async def dequeue(self) -> TicketProcessJob | None:
        return None

    async def ack(self, job_id: UUID) -> None:
        _ = job_id
        return None


def assert_queue_protocol() -> None:
    """Runtime hook to keep `NullJobQueue` aligned with `JobQueue` during refactors."""
    _: JobQueue = NullJobQueue()
