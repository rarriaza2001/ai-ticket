"""Postgres seed logic for Phase 4 benchmarks."""

from __future__ import annotations

import os
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from phase4_benchmark.common import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    SEED_SOURCE,
    deterministic_vector,
    status_for_index,
    text_hash,
)
from phase4_benchmark.manifest import SeedManifest
from phase4_benchmark.paths import find_repo_root, manifest_path as default_manifest_path

DEFAULT_DATABASE_URL = "postgresql://ticket:ticket@localhost:5433/tickets"


def async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def clear_seed_data(session: AsyncSession) -> None:
    await session.execute(
        text(
            "DELETE FROM draft_suggestions WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE source = :source)"
        ),
        {"source": SEED_SOURCE},
    )
    await session.execute(
        text(
            "DELETE FROM ticket_events WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE source = :source)"
        ),
        {"source": SEED_SOURCE},
    )
    await session.execute(
        text(
            "DELETE FROM routing_decisions WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE source = :source)"
        ),
        {"source": SEED_SOURCE},
    )
    await session.execute(
        text(
            "DELETE FROM ticket_embeddings WHERE ticket_id IN "
            "(SELECT id FROM tickets WHERE source = :source)"
        ),
        {"source": SEED_SOURCE},
    )
    await session.execute(text("DELETE FROM tickets WHERE source = :source"), {"source": SEED_SOURCE})


async def seed_database(
    session: AsyncSession,
    *,
    size: int,
    api_root: Path,
) -> SeedManifest:
    # Import ORM models from api-service (caller must have api_root on sys.path).
    from app.db.models.draft_suggestion import DraftSuggestion
    from app.db.models.routing_decision import RoutingDecision
    from app.db.models.ticket import Ticket
    from app.db.models.ticket_embedding import TicketEmbedding
    from app.db.models.ticket_event import TicketEvent
    from app.domain.enums import DecidedBy, RoutingDecisionType, TicketEventType

    now = datetime.now(UTC)
    status_counts: Counter[str] = Counter()
    sample_ticket_id: uuid.UUID | None = None
    sample_with_draft_id: uuid.UUID | None = None

    for i in range(size):
        status = status_for_index(i, size)
        status_counts[status] += 1
        subject = f"Phase4 benchmark ticket {i:05d}"
        body = f"Deterministic seed body for ticket index {i}."
        ticket = Ticket(
            source=SEED_SOURCE,
            subject=subject,
            body=body,
            status=status,
            external_id=f"phase4-bench-{i:05d}",
            created_at=now,
            updated_at=now,
        )
        session.add(ticket)
        await session.flush()

        if sample_ticket_id is None and status == "routed":
            sample_ticket_id = ticket.id

        session.add(
            TicketEvent(
                ticket_id=ticket.id,
                event_type=TicketEventType.TICKET_RECEIVED.value,
                payload={"status": status, "seed_index": i},
                created_at=now,
            )
        )

        if status in ("embedded", "routing_pending", "routed"):
            vec = deterministic_vector(i)
            session.add(
                TicketEmbedding(
                    ticket_id=ticket.id,
                    embedding=vec,
                    embedding_model=DEFAULT_EMBEDDING_MODEL,
                    embedding_dimension=EMBEDDING_DIMENSION,
                    source_text_hash=text_hash(subject, body),
                    is_active=True,
                    embedded_at=now,
                    created_at=now,
                )
            )
            session.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    event_type=TicketEventType.EMBEDDING_STORED.value,
                    payload={"seed_index": i},
                    created_at=now,
                )
            )

        if status in ("routing_pending", "routed"):
            for decision_type, route_to in (
                (RoutingDecisionType.CATEGORY.value, "billing"),
                (RoutingDecisionType.TEAM.value, "tier1"),
                (RoutingDecisionType.PRIORITY.value, "normal"),
                (RoutingDecisionType.ESCALATION.value, "none"),
            ):
                session.add(
                    RoutingDecision(
                        ticket_id=ticket.id,
                        route_to=route_to,
                        decision_type=decision_type,
                        decided_by=DecidedBy.TEST_SEED.value,
                        confidence=Decimal("0.85"),
                        reason=None,
                        created_at=now,
                    )
                )

        if status == "routed" and i % 3 == 0:
            session.add(
                DraftSuggestion(
                    ticket_id=ticket.id,
                    draft_text=f"Seed draft suggestion for ticket {i}.",
                    provider_name="mock",
                    model_name="mock-suggestion-v1",
                    prompt_version="phase4-seed-v1",
                    status="pending_review",
                    confidence=Decimal("0.72"),
                    requires_human_review=True,
                    created_at=now,
                )
            )
            if sample_with_draft_id is None:
                sample_with_draft_id = ticket.id

        if status == "routed":
            session.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    event_type=TicketEventType.AI_PROCESSING_COMPLETED.value,
                    payload={"seed_index": i},
                    created_at=now,
                )
            )
        elif status == "failed":
            session.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    event_type=TicketEventType.AI_PROCESSING_FAILED.value,
                    payload={"seed_index": i},
                    created_at=now,
                )
            )

    if sample_ticket_id is None:
        raise RuntimeError("No routed ticket seeded; cannot build manifest")

    return SeedManifest.build(
        dataset_size_label="",  # filled by caller
        dataset_ticket_count=size,
        sample_ticket_id=sample_ticket_id,
        sample_ticket_with_draft_id=sample_with_draft_id or sample_ticket_id,
        status_counts=dict(status_counts),
        similar_query_index=0,
        seed_source=SEED_SOURCE,
    )


async def run_migrations(database_url: str, api_root: Path) -> None:
    os.environ["DATABASE_URL"] = database_url
    prev_cwd = Path.cwd()
    os.chdir(api_root)
    try:
        cfg = Config(str(api_root / "alembic.ini"))
        command.upgrade(cfg, "head")
    finally:
        os.chdir(prev_cwd)


async def run_seed(
    *,
    size_label: str,
    ticket_count: int,
    database_url: str,
    api_root: Path,
    reset: bool,
    skip_migrations: bool,
    manifest_path: Path,
) -> SeedManifest:
    if not skip_migrations:
        await run_migrations(database_url, api_root)

    engine = create_async_engine(async_url(database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            if reset:
                await clear_seed_data(session)
                await session.commit()
            manifest = await seed_database(session, size=ticket_count, api_root=api_root)
            manifest.dataset_size_label = size_label
            await session.commit()
        manifest.write(manifest_path.resolve())
        return manifest
    finally:
        await engine.dispose()
