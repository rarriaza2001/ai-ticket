from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.routing_decision import RoutingDecision


class RoutingDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        route_to: str,
        decision_type: str,
        decided_by: str,
        confidence: Decimal | None = None,
        reason: str | None = None,
    ) -> RoutingDecision:
        decision = RoutingDecision(
            ticket_id=ticket_id,
            route_to=route_to,
            decision_type=decision_type,
            decided_by=decided_by,
            confidence=confidence,
            reason=reason,
        )
        self._session.add(decision)
        await self._session.flush()
        return decision

    async def get_latest_for_ticket(self, ticket_id: uuid.UUID) -> RoutingDecision | None:
        result = await self._session.execute(
            select(RoutingDecision)
            .where(RoutingDecision.ticket_id == ticket_id)
            .order_by(RoutingDecision.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
