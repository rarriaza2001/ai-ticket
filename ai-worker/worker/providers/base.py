from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from shared_contracts import SuggestionMetadata


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    team: str
    priority: str
    escalation: str
    classification_confidence: float
    routing_confidence: float
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model_name: str
    provider_name: str
    embedding_dimension: int


@dataclass(frozen=True)
class SimilarTicketContext:
    ticket_id: str
    subject: str
    status: str
    distance: float
    body_excerpt: str


@dataclass(frozen=True)
class DraftSuggestionResult:
    draft_text: str
    confidence: float
    model_name: str
    provider_name: str
    metadata: SuggestionMetadata | None = None


class AiProvider(ABC):
    provider_name: str

    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResult:
        raise NotImplementedError

    @abstractmethod
    async def classify(
        self, *, subject: str, body: str, prompt: str
    ) -> ClassificationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_draft_suggestion(
        self,
        *,
        subject: str,
        body: str,
        similar_context: list[SimilarTicketContext],
        prompt: str,
    ) -> DraftSuggestionResult:
        raise NotImplementedError
