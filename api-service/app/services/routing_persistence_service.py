from __future__ import annotations

import uuid
from decimal import Decimal

from app.core.errors import TicketNotFound
from app.db.models.routing_decision import RoutingDecision
from app.domain.enums import TicketEventType, TicketStatus
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository


class RoutingPersistenceService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        routing_decision_repository: RoutingDecisionRepository,
        ticket_event_repository: TicketEventRepository,
    ) -> None:
        self._tickets = ticket_repository
        self._routing = routing_decision_repository
        self._events = ticket_event_repository

    async def store_routing_decision(
        self,
        ticket_id: uuid.UUID,
        *,
        route_to: str,
        decision_type: str,
        decided_by: str,
        confidence: Decimal | None = None,
        reason: str | None = None,
    ) -> RoutingDecision:
        if await self._tickets.get_by_id(ticket_id) is None:
            raise TicketNotFound(ticket_id)

        decision = await self._routing.create(
            ticket_id=ticket_id,
            route_to=route_to,
            decision_type=decision_type,
            decided_by=decided_by,
            confidence=confidence,
            reason=reason,
        )
        await self._tickets.update_status(ticket_id, TicketStatus.ROUTED.value)
        await self._events.append(
            ticket_id,
            TicketEventType.ROUTING_DECISION_STORED.value,
            payload={
                "routing_decision_id": str(decision.id),
                "route_to": route_to,
                "decision_type": decision_type,
            },
        )
        return decision
