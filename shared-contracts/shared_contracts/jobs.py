from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TicketProcessJob(BaseModel):
    """Queue envelope for asynchronous ticket processing (at-least-once; worker must be idempotent)."""

    ticket_id: UUID
    job_id: UUID = Field(description="Unique job instance id.")
    dedupe_key: str = Field(description="Business-level dedupe (e.g. idempotency key).")
    requested_at: datetime
