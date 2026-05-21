from __future__ import annotations

import time
import uuid

import structlog
from shared_contracts import AiPipelineObservability
from sqlalchemy.ext.asyncio import AsyncSession

from worker.core.config import Settings
from worker.domain.enums import TicketEventType, TicketStatus
from worker.providers.base import AiProvider
from worker.providers.factory import create_ai_provider
from worker.repositories.draft_suggestion_repository import DraftSuggestionRepository
from worker.repositories.routing_decision_repository import RoutingDecisionRepository
from worker.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from worker.repositories.ticket_event_repository import TicketEventRepository
from worker.repositories.ticket_repository import TicketRepository
from worker.services.classification_service import ClassificationService
from worker.services.embedding_service import EmbeddingService
from worker.services.retrieval_service import RetrievalService
from worker.services.suggestion_service import SuggestionService

logger = structlog.get_logger(__name__)


class AiWorkflowService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: AiProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider or create_ai_provider(settings)

        tickets = TicketRepository(session)
        embeddings = TicketEmbeddingRepository(session)
        routing = RoutingDecisionRepository(session)
        events = TicketEventRepository(session)
        drafts = DraftSuggestionRepository(session)

        self._tickets = tickets
        self._events = events
        self._embedding_svc = EmbeddingService(
            provider=self._provider,
            settings=settings,
            tickets=tickets,
            embeddings=embeddings,
            events=events,
        )
        self._classification_svc = ClassificationService(
            provider=self._provider,
            settings=settings,
            tickets=tickets,
            routing=routing,
            events=events,
        )
        self._retrieval_svc = RetrievalService(
            settings=settings,
            embeddings=embeddings,
            events=events,
        )
        self._suggestion_svc = SuggestionService(
            provider=self._provider,
            settings=settings,
            drafts=drafts,
            events=events,
        )

    async def process_ticket(self, ticket_id: uuid.UUID) -> None:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            logger.warning("ai.workflow.ticket_not_found", ticket_id=str(ticket_id))
            return
        if ticket.status in (TicketStatus.ROUTED.value, TicketStatus.FAILED.value):
            return

        pipeline_started = time.perf_counter()

        try:
            await self._events.append(
                ticket_id,
                TicketEventType.AI_PROCESSING_STARTED.value,
                payload={"status": ticket.status},
            )

            query_vec, embedding_model, embedding_dimension, provider_name, embed_ms = (
                await self._embedding_svc.ensure_embedding(ticket)
            )

            parsed, classify_ms = await self._classification_svc.classify_and_persist(ticket)

            usable, weak, retrieval_ms = await self._retrieval_svc.find_usable_matches(
                ticket_id,
                query_vec,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )

            draft_created = False
            suggest_ms = 0.0
            if usable:
                draft_created, suggest_ms = await self._suggestion_svc.maybe_create_suggestion(
                    ticket, usable
                )

            await self._tickets.update_status(ticket_id, TicketStatus.ROUTED.value)
            total_ms = (time.perf_counter() - pipeline_started) * 1000

            observability = AiPipelineObservability(
                embedding_latency_ms=embed_ms or None,
                classification_latency_ms=classify_ms,
                retrieval_latency_ms=retrieval_ms,
                suggestion_latency_ms=suggest_ms if draft_created else None,
                total_latency_ms=total_ms,
                provider_name=provider_name,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
                similarity_match_count=len(usable),
                top_similarity_distance=usable[0].distance if usable else None,
                confidence=parsed.classification_confidence,
                fallback_reason=parsed.fallback_reason,
                requires_human_review=parsed.requires_human_review,
            )

            payload = observability.model_dump(exclude_none=True)
            payload["category"] = parsed.category
            payload["routing_confidence"] = parsed.routing_confidence
            payload["weak_match_count"] = len(weak)
            payload["draft_created"] = draft_created

            await self._events.append(
                ticket_id,
                TicketEventType.AI_PROCESSING_COMPLETED.value,
                payload=payload,
            )

            logger.info("ai.workflow.completed", ticket_id=str(ticket_id), **payload)
        except Exception as exc:
            await self._tickets.update_status(ticket_id, TicketStatus.FAILED.value)
            await self._events.append(
                ticket_id,
                TicketEventType.AI_PROCESSING_FAILED.value,
                payload={
                    "failure_reason": type(exc).__name__,
                    "message": str(exc)[:200],
                },
            )
            logger.exception(
                "ai.workflow.failed",
                ticket_id=str(ticket_id),
                failure_reason=type(exc).__name__,
            )
