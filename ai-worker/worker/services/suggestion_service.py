from __future__ import annotations

import time

from shared_contracts import SuggestionStatus

from worker.core.config import Settings
from worker.db.models.ticket import Ticket
from worker.domain.enums import TicketEventType
from worker.prompts import PROMPT_VERSION, load_suggestion_prompt
from worker.providers.base import AiProvider
from worker.repositories.draft_suggestion_repository import DraftSuggestionRepository
from worker.repositories.ticket_embedding_repository import SimilarTicketRow
from worker.repositories.ticket_event_repository import TicketEventRepository
from worker.services.embedding_service import _with_retries


class SuggestionService:
    def __init__(
        self,
        *,
        provider: AiProvider,
        settings: Settings,
        drafts: DraftSuggestionRepository,
        events: TicketEventRepository,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._drafts = drafts
        self._events = events

    async def maybe_create_suggestion(
        self,
        ticket: Ticket,
        usable_matches: list[SimilarTicketRow],
    ) -> tuple[bool, float]:
        if not usable_matches:
            return False, 0.0
        if await self._drafts.has_pending_review(ticket.id):
            return False, 0.0

        prompt = load_suggestion_prompt()
        similar_subjects = [m.subject for m in usable_matches]
        similar_ticket_ids = [str(m.ticket_id) for m in usable_matches]
        started = time.perf_counter()

        async def _suggest():
            return await self._provider.generate_draft_suggestion(
                subject=ticket.subject,
                body=ticket.body,
                similar_subjects=similar_subjects,
                similar_ticket_ids=similar_ticket_ids,
                prompt=prompt,
            )

        result = await _with_retries(_suggest, max_retries=self._settings.suggestion_max_retries)
        latency_ms = (time.perf_counter() - started) * 1000

        from decimal import Decimal

        await self._drafts.create(
            ticket_id=ticket.id,
            draft_text=result.draft_text,
            provider_name=result.provider_name,
            model_name=result.model_name,
            prompt_version=PROMPT_VERSION,
            status=SuggestionStatus.PENDING_REVIEW.value,
            confidence=Decimal(str(round(result.confidence, 4))),
            requires_human_review=True,
        )
        await self._events.append(
            ticket.id,
            TicketEventType.DRAFT_SUGGESTION_STORED.value,
            payload={
                "provider": result.provider_name,
                "model": result.model_name,
                "prompt_version": PROMPT_VERSION,
                "draft_length": len(result.draft_text),
                "requires_human_review": True,
                "usable_context_count": len(usable_matches),
            },
        )
        return True, latency_ms
