from __future__ import annotations

from app.db.models.ticket import Ticket
from app.domain.enums import TicketEventType, TicketStatus
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository


class TicketIntakeService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        ticket_event_repository: TicketEventRepository,
    ) -> None:
        self._tickets = ticket_repository
        self._events = ticket_event_repository

    async def create_ticket(
        self,
        *,
        source: str,
        subject: str,
        body: str,
        external_id: str | None = None,
        customer_email: str | None = None,
        priority: str | None = None,
    ) -> Ticket:
        ticket = await self._tickets.create(
            source=source,
            subject=subject,
            body=body,
            status=TicketStatus.PENDING_EMBEDDING.value,
            external_id=external_id,
            customer_email=customer_email,
            priority=priority,
        )
        await self._events.append(
            ticket.id,
            TicketEventType.TICKET_RECEIVED.value,
            payload={"status": ticket.status},
        )
        return ticket
