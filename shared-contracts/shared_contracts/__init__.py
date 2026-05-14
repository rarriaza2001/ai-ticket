"""Shared contracts for api-service and ai-worker."""

from shared_contracts.enums import TicketStatus
from shared_contracts.jobs import TicketProcessJob
from shared_contracts.models import (
    RoutingDecision,
    SimilarTicketSnapshot,
    Ticket,
    TicketCreateRequest,
    TicketEmbedding,
    TicketEvent,
    TicketSuggestion,
)
from shared_contracts.protocols import JobQueue, TicketEnqueueProtocol
from shared_contracts.version import __version__

__all__ = [
    "__version__",
    "JobQueue",
    "RoutingDecision",
    "SimilarTicketSnapshot",
    "Ticket",
    "TicketCreateRequest",
    "TicketEmbedding",
    "TicketEvent",
    "TicketProcessJob",
    "TicketStatus",
    "TicketSuggestion",
    "TicketEnqueueProtocol",
]
