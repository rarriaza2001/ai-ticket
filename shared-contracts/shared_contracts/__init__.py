"""Shared contracts for api-service and ai-worker."""

from shared_contracts.ai import (
    AiPipelineObservability,
    AiTicketEventType,
    SuggestionStatus,
)
from shared_contracts.classification import ClassificationOutput, SuggestionMetadata
from shared_contracts.foundation import HealthResponse, ReadinessResponse
from shared_contracts.taxonomy import SupportTeam, TicketCategory, TicketPriority
from shared_contracts.version import __version__

__all__ = [
    "__version__",
    "HealthResponse",
    "ReadinessResponse",
    "SuggestionStatus",
    "AiTicketEventType",
    "AiPipelineObservability",
    "TicketCategory",
    "SupportTeam",
    "TicketPriority",
    "ClassificationOutput",
    "SuggestionMetadata",
]
