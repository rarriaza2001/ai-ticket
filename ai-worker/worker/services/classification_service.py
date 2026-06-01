from __future__ import annotations

import time
from decimal import Decimal

from worker.core.config import Settings
from worker.db.models.ticket import Ticket
from worker.domain.enums import DecidedBy, RoutingDecisionType, TicketEventType, TicketStatus
from worker.providers.base import AiProvider
from worker.providers.errors import MalformedModelOutput
from worker.prompts import PROMPT_VERSION, load_classification_prompt
from worker.cache.ticket_cache_invalidator import TicketCacheInvalidator
from worker.repositories.routing_decision_repository import RoutingDecisionRepository
from worker.repositories.ticket_event_repository import TicketEventRepository
from worker.repositories.ticket_repository import TicketRepository
from worker.services.classification_policy import (
    ParsedClassification,
    apply_classification_policy,
    fallback_classification,
    validate_raw_classification,
)
from worker.services.embedding_service import _with_retries
from worker.services.text_preparation import prepare_ticket_text


class ClassificationService:
    def __init__(
        self,
        *,
        provider: AiProvider,
        settings: Settings,
        tickets: TicketRepository,
        routing: RoutingDecisionRepository,
        events: TicketEventRepository,
        cache_invalidator: TicketCacheInvalidator | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._tickets = tickets
        self._routing = routing
        self._events = events
        self._cache_invalidator = cache_invalidator

    async def classify_and_persist(self, ticket: Ticket) -> tuple[ParsedClassification, float]:
        prepared = prepare_ticket_text(ticket.subject, ticket.body)
        prompt = load_classification_prompt()
        started = time.perf_counter()
        parsed: ParsedClassification | None = None
        json_retried = False
        last_exc: Exception | None = None

        for attempt in range(self._settings.classification_max_retries + 1):
            try:

                async def _classify():
                    return await self._provider.classify(
                        subject=prepared.subject,
                        body=prepared.body,
                        prompt=prompt,
                    )

                raw = await _with_retries(
                    _classify,
                    max_retries=0,
                )
                validated = validate_raw_classification(raw)
                parsed = apply_classification_policy(
                    validated,
                    confidence_high=self._settings.classification_confidence_high,
                    confidence_medium=self._settings.classification_confidence_medium,
                    routing_confidence_min=self._settings.routing_confidence_min,
                )
                break
            except MalformedModelOutput as exc:
                last_exc = exc
                if not json_retried:
                    json_retried = True
                    continue
                parsed = fallback_classification(reason="malformed_model_output")
                break
            except Exception as exc:
                last_exc = exc
                if attempt >= self._settings.classification_max_retries:
                    parsed = fallback_classification(reason="classification_provider_error")
                    break

        if parsed is None:
            _ = last_exc
            parsed = fallback_classification(reason="classification_exhausted_retries")

        latency_ms = (time.perf_counter() - started) * 1000

        confidence_dec = Decimal(str(round(parsed.classification_confidence, 4)))
        routing_conf_dec = Decimal(str(round(parsed.routing_confidence, 4)))
        reason = parsed.fallback_reason or (
            "human_review_required" if parsed.requires_human_review else None
        )
        decided_by = DecidedBy.WORKER.value

        decisions = (
            (RoutingDecisionType.CATEGORY.value, parsed.category, confidence_dec),
            (RoutingDecisionType.TEAM.value, parsed.team, routing_conf_dec),
            (RoutingDecisionType.PRIORITY.value, parsed.priority, confidence_dec),
            (RoutingDecisionType.ESCALATION.value, parsed.escalation, confidence_dec),
        )
        for decision_type, route_to, confidence in decisions:
            await self._routing.create(
                ticket_id=ticket.id,
                route_to=route_to,
                decision_type=decision_type,
                decided_by=decided_by,
                confidence=confidence,
                reason=reason,
            )

        await self._tickets.update_status(ticket.id, TicketStatus.ROUTING_PENDING.value)
        await self._events.append(
            ticket.id,
            TicketEventType.CLASSIFICATION_COMPLETED.value,
            payload={
                "category": parsed.category,
                "team": parsed.team,
                "priority": parsed.priority,
                "classification_confidence": parsed.classification_confidence,
                "routing_confidence": parsed.routing_confidence,
                "requires_human_review": parsed.requires_human_review,
                "fallback_reason": parsed.fallback_reason,
                "prompt_version": PROMPT_VERSION,
            },
        )
        if self._cache_invalidator is not None:
            await self._cache_invalidator.invalidate_routing(ticket.id)
            await self._cache_invalidator.invalidate_status(ticket.id)
            await self._cache_invalidator.invalidate_events(ticket.id)
        return parsed, latency_ms
