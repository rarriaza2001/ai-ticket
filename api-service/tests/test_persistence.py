from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from app.domain.enums import TicketEventType, TicketStatus
from app.repositories.routing_decision_repository import RoutingDecisionRepository
from app.repositories.ticket_embedding_repository import TicketEmbeddingRepository
from app.repositories.ticket_event_repository import TicketEventRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.routing_persistence_service import RoutingPersistenceService
from app.services.ticket_intake_service import TicketIntakeService


@pytest.mark.asyncio
async def test_migration_creates_tables_and_vector_extension(
    db_session: AsyncSession,
) -> None:
    tables = await db_session.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename IN "
            "('tickets', 'ticket_embeddings', 'routing_decisions', 'ticket_events')"
        )
    )
    names = {row[0] for row in tables.all()}
    assert names == {"tickets", "ticket_embeddings", "routing_decisions", "ticket_events"}

    ext = await db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    assert ext.scalar_one_or_none() == "vector"


@pytest.mark.asyncio
async def test_ticket_intake_creates_pending_embedding_and_event(
    db_session: AsyncSession,
) -> None:
    tickets = TicketRepository(db_session)
    events = TicketEventRepository(db_session)
    service = TicketIntakeService(tickets, events)

    ticket = await service.create_ticket(
        source="email",
        subject="Help",
        body="My app is broken",
    )
    await db_session.commit()

    assert ticket.status == TicketStatus.PENDING_EMBEDDING.value
    trail = await events.list_for_ticket(ticket.id)
    assert len(trail) == 1
    assert trail[0].event_type == TicketEventType.TICKET_RECEIVED.value


@pytest.mark.asyncio
async def test_embedding_store_and_one_active_per_ticket(
    db_session: AsyncSession,
    fake_embedding: list[float],
    fake_embedding_alt: list[float],
) -> None:
    tickets = TicketRepository(db_session)
    embeddings = TicketEmbeddingRepository(db_session)
    events = TicketEventRepository(db_session)
    intake = TicketIntakeService(tickets, events)
    embed_svc = EmbeddingPersistenceService(tickets, embeddings, events)

    ticket = await intake.create_ticket(source="api", subject="A", body="Body A")
    await embed_svc.store_ticket_embedding(
        ticket.id,
        embedding=fake_embedding,
        source_text_hash="hash-a",
    )
    first_id = (await embeddings.search_similar(fake_embedding, limit=1))[0].embedding_id

    await embed_svc.store_ticket_embedding(
        ticket.id,
        embedding=fake_embedding_alt,
        source_text_hash="hash-b",
    )
    await db_session.commit()

    assert await embeddings.has_active_embedding(ticket.id)
    rows = await embeddings.search_similar(fake_embedding_alt, limit=5)
    active_rows = [r for r in rows if r.ticket_id == ticket.id]
    assert len(active_rows) == 1
    assert active_rows[0].embedding_id != first_id


@pytest.mark.asyncio
async def test_similarity_search_only_active_embeddings(
    db_session: AsyncSession,
    fake_embedding: list[float],
    fake_embedding_alt: list[float],
) -> None:
    tickets = TicketRepository(db_session)
    embeddings = TicketEmbeddingRepository(db_session)
    events = TicketEventRepository(db_session)
    intake = TicketIntakeService(tickets, events)
    embed_svc = EmbeddingPersistenceService(tickets, embeddings, events)

    t1 = await intake.create_ticket(source="s", subject="T1", body="b1")
    t2 = await intake.create_ticket(source="s", subject="T2", body="b2")
    await embed_svc.store_ticket_embedding(t1.id, embedding=fake_embedding, source_text_hash="h1")
    await embed_svc.store_ticket_embedding(t2.id, embedding=fake_embedding_alt, source_text_hash="h2")
    await embeddings.deactivate_active_for_ticket(t2.id)
    await db_session.commit()

    results = await embeddings.search_similar(
        fake_embedding_alt,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=EMBEDDING_DIMENSION,
    )
    ticket_ids = {r.ticket_id for r in results}
    assert t2.id not in ticket_ids
    assert t1.id in ticket_ids


@pytest.mark.asyncio
async def test_latest_routing_decision_and_audit_trail(
    db_session: AsyncSession,
    fake_embedding: list[float],
) -> None:
    tickets = TicketRepository(db_session)
    embeddings = TicketEmbeddingRepository(db_session)
    events = TicketEventRepository(db_session)
    routing_repo = RoutingDecisionRepository(db_session)
    intake = TicketIntakeService(tickets, events)
    embed_svc = EmbeddingPersistenceService(tickets, embeddings, events)
    route_svc = RoutingPersistenceService(tickets, routing_repo, events)

    ticket = await intake.create_ticket(source="s", subject="R", body="b")
    await embed_svc.store_ticket_embedding(
        ticket.id, embedding=fake_embedding, source_text_hash="h"
    )
    await route_svc.store_routing_decision(
        ticket.id,
        route_to="billing",
        decision_type="team",
        decided_by="test_seed",
        confidence=Decimal("0.9"),
    )
    await db_session.commit()

    latest = await routing_repo.get_latest_for_ticket(ticket.id)
    assert latest is not None
    assert latest.route_to == "billing"

    trail = await events.list_for_ticket(ticket.id)
    event_types = [e.event_type for e in trail]
    assert TicketEventType.TICKET_RECEIVED.value in event_types
    assert TicketEventType.EMBEDDING_STORED.value in event_types
    assert TicketEventType.ROUTING_DECISION_STORED.value in event_types


@pytest.mark.asyncio
async def test_api_create_and_get_ticket(client: AsyncClient) -> None:
    response = await client.post(
        "/tickets",
        json={
            "source": "email",
            "subject": "API ticket",
            "body": "From httpx test",
        },
    )
    assert response.status_code == 201
    data = response.json()
    ticket_id = data["id"]
    assert data["status"] == TicketStatus.PENDING_EMBEDDING.value

    get_resp = await client.get(f"/tickets/{ticket_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["subject"] == "API ticket"

    events_resp = await client.get(f"/tickets/{ticket_id}/events")
    assert events_resp.status_code == 200
    assert len(events_resp.json()) == 1


@pytest.mark.asyncio
async def test_api_similarity_search(
    client: AsyncClient,
    fake_embedding: list[float],
    fake_embedding_alt: list[float],
) -> None:
    create = await client.post(
        "/tickets",
        json={"source": "s", "subject": "Near", "body": "b"},
    )
    ticket_id = create.json()["id"]
    await client.post(
        f"/tickets/{ticket_id}/embeddings/test",
        json={"embedding": fake_embedding},
    )

    far = await client.post(
        "/tickets",
        json={"source": "s", "subject": "Far", "body": "b2"},
    )
    far_id = far.json()["id"]
    await client.post(
        f"/tickets/{far_id}/embeddings/test",
        json={"embedding": fake_embedding_alt},
    )

    similar = await client.post(
        "/tickets/similar",
        json={"embedding": fake_embedding, "limit": 5},
    )
    assert similar.status_code == 200
    results = similar.json()["results"]
    assert any(r["ticket_id"] == ticket_id for r in results)


@pytest.mark.asyncio
async def test_api_ticket_not_found(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    resp = await client.get(f"/tickets/{missing}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ticket_not_found"
