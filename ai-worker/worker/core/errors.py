from __future__ import annotations

import uuid


class TicketNotFound(Exception):
    def __init__(self, ticket_id: uuid.UUID) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"Ticket not found: {ticket_id}")
