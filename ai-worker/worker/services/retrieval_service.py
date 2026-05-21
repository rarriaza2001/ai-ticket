from __future__ import annotations

import time
import uuid

from worker.core.config import Settings
from worker.domain.enums import TicketEventType
from worker.repositories.ticket_embedding_repository import (
    SimilarTicketRow,
    TicketEmbeddingRepository,
)
from worker.repositories.ticket_event_repository import TicketEventRepository


class RetrievalService:
    def __init__(
        self,
        *,
        settings: Settings,
        embeddings: TicketEmbeddingRepository,
        events: TicketEventRepository,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._events = events

    async def find_usable_matches(
        self,
        ticket_id: uuid.UUID,
        query_embedding: list[float],
        *,
        embedding_model: str,
        embedding_dimension: int,
    ) -> tuple[list[SimilarTicketRow], list[SimilarTicketRow], float]:
        """Return (usable_matches, weak_matches, latency_ms)."""
        started = time.perf_counter()
        rows = await self._embeddings.search_similar(
            query_embedding,
            limit=self._settings.retrieval_top_k,
            exclude_ticket_id=ticket_id,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            max_ticket_age_days=self._settings.retrieval_context_max_age_days,
        )
        usable = [
            r for r in rows if r.distance <= self._settings.retrieval_usable_max_distance
        ]
        weak = [
            r for r in rows if r.distance > self._settings.retrieval_usable_max_distance
        ]
        latency_ms = (time.perf_counter() - started) * 1000

        top_usable_distance = usable[0].distance if usable else None
        await self._events.append(
            ticket_id,
            TicketEventType.RETRIEVAL_COMPLETED.value,
            payload={
                "usable_count": len(usable),
                "weak_count": len(weak),
                "raw_match_count": len(rows),
                "top_usable_distance": top_usable_distance,
                "max_usable_distance": self._settings.retrieval_usable_max_distance,
                "stale_excluded": True,
                "max_age_days": self._settings.retrieval_context_max_age_days,
            },
        )
        return usable, weak, latency_ms
