from __future__ import annotations

import hashlib
import math

from shared_contracts import SuggestionMetadata, SupportTeam, TicketCategory, TicketPriority
from worker.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from worker.providers.base import (
    AiProvider,
    ClassificationResult,
    DraftSuggestionResult,
    EmbeddingResult,
    SimilarTicketContext,
)
from worker.providers.errors import MalformedModelOutput


def _hash_embedding(text: str) -> list[float]:
    """Deterministic unit-ish vector from text (no external API)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = [0.0] * EMBEDDING_DIMENSION
    for i in range(min(EMBEDDING_DIMENSION, len(digest))):
        vec[i] = (digest[i] / 255.0) * 2 - 1
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class MockAiProvider(AiProvider):
    provider_name = "mock"

    def __init__(
        self,
        *,
        force_malformed: bool = False,
        force_low_confidence: bool = False,
        force_low_routing_confidence: bool = False,
    ) -> None:
        self.force_malformed = force_malformed
        self.force_low_confidence = force_low_confidence
        self.force_low_routing_confidence = force_low_routing_confidence
        self.call_counts: dict[str, int] = {
            "embed": 0,
            "classify": 0,
            "suggest": 0,
        }

    async def embed_text(self, text: str) -> EmbeddingResult:
        self.call_counts["embed"] += 1
        return EmbeddingResult(
            vector=_hash_embedding(text),
            model_name=DEFAULT_EMBEDDING_MODEL,
            provider_name=self.provider_name,
            embedding_dimension=EMBEDDING_DIMENSION,
        )

    async def classify(self, *, subject: str, body: str, prompt: str) -> ClassificationResult:
        self.call_counts["classify"] += 1
        _ = prompt, subject, body
        if self.force_malformed:
            raise MalformedModelOutput("mock malformed output")
        classification_confidence = 0.55 if self.force_low_confidence else 0.85
        routing_confidence = 0.55 if self.force_low_routing_confidence else 0.85
        return ClassificationResult(
            category=TicketCategory.BILLING.value,
            team=SupportTeam.BILLING_SUPPORT.value,
            priority=TicketPriority.NORMAL.value,
            escalation="none",
            classification_confidence=classification_confidence,
            routing_confidence=routing_confidence,
            raw={"subject_len": len(subject), "body_len": len(body)},
        )

    async def generate_draft_suggestion(
        self,
        *,
        subject: str,
        body: str,
        similar_context: list[SimilarTicketContext],
        prompt: str,
    ) -> DraftSuggestionResult:
        self.call_counts["suggest"] += 1
        _ = prompt
        if similar_context:
            peer = similar_context[0]
            context_hint = (
                f"{peer.subject[:40]} status={peer.status} "
                f"distance={peer.distance:.2f} excerpt={peer.body_excerpt[:60]}"
            )
            ticket_hint = peer.ticket_id
        else:
            context_hint = "none"
            ticket_hint = "none"
        draft = (
            f"[SUGGESTION for human review] Re: {subject[:80]} — "
            f"based on similar ticket ({ticket_hint}): {context_hint}. "
            f"(body length {len(body)})"
        )
        return DraftSuggestionResult(
            draft_text=draft,
            confidence=0.75,
            model_name="gpt-4.1-mini",
            provider_name=self.provider_name,
            metadata=SuggestionMetadata(summary="Mock draft", key_points=["human review required"]),
        )
