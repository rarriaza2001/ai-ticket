from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from worker.db.base import Base

if TYPE_CHECKING:
    from worker.db.models.draft_suggestion import DraftSuggestion
    from worker.db.models.routing_decision import RoutingDecision
    from worker.db.models.ticket_embedding import TicketEmbedding
    from worker.db.models.ticket_event import TicketEvent


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    customer_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    embeddings: Mapped[list[TicketEmbedding]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    events: Mapped[list[TicketEvent]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    routing_decisions: Mapped[list[RoutingDecision]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    draft_suggestions: Mapped[list[DraftSuggestion]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
