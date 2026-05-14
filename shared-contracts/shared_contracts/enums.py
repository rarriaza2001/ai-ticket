from enum import StrEnum


class TicketStatus(StrEnum):
    """Lifecycle states for support tickets (authoritative values in Postgres)."""

    RECEIVED = "received"
    PENDING_PROCESSING = "pending_processing"
    PROCESSING = "processing"
    ROUTED = "routed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    FAILED = "failed"
