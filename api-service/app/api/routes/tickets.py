from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.schemas.tickets import (
    CreateTicketRequest,
    DraftSuggestionResponse,
    RoutingDecisionResponse,
    SimilarTicketResult,
    SimilarTicketsRequest,
    SimilarTicketsResponse,
    StoreTestEmbeddingRequest,
    TicketEmbeddingResponse,
    TicketEventResponse,
    TicketResponse,
    TicketStatusResponse,
)
from app.core.embedding import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from app.deps import (
    EmbeddingPersistenceSvc,
    TicketIntakeSvc,
    TicketQuerySvc,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: CreateTicketRequest,
    service: TicketIntakeSvc,
) -> TicketResponse:
    ticket = await service.create_ticket(
        source=body.source,
        subject=body.subject,
        body=body.body,
        external_id=body.external_id,
        customer_email=body.customer_email,
        priority=body.priority,
    )
    return TicketResponse.model_validate(ticket)


@router.post("/similar", response_model=SimilarTicketsResponse)
async def search_similar_tickets(
    body: SimilarTicketsRequest,
    service: TicketQuerySvc,
) -> SimilarTicketsResponse:
    rows = await service.search_similar_tickets(
        body.embedding,
        limit=body.limit,
        exclude_ticket_id=body.exclude_ticket_id,
        embedding_model=body.embedding_model,
        embedding_dimension=body.embedding_dimension,
    )
    return SimilarTicketsResponse(
        results=[
            SimilarTicketResult(
                ticket_id=row.ticket_id,
                embedding_id=row.embedding_id,
                subject=row.subject,
                source=row.source,
                status=row.status,
                distance=row.distance,
            )
            for row in rows
        ]
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    service: TicketQuerySvc,
) -> TicketResponse:
    ticket = await service.get_ticket(ticket_id)
    return TicketResponse.model_validate(ticket)


@router.get("/{ticket_id}/status", response_model=TicketStatusResponse)
async def get_ticket_status(
    ticket_id: uuid.UUID,
    service: TicketQuerySvc,
) -> TicketStatusResponse:
    ticket_status = await service.get_ticket_status(ticket_id)
    return TicketStatusResponse(ticket_id=ticket_id, status=ticket_status)


@router.get("/{ticket_id}/events", response_model=list[TicketEventResponse])
async def get_ticket_events(
    ticket_id: uuid.UUID,
    service: TicketQuerySvc,
) -> list[TicketEventResponse]:
    events = await service.get_audit_trail(ticket_id)
    return [TicketEventResponse.model_validate(e) for e in events]


@router.get("/{ticket_id}/routing-decision", response_model=RoutingDecisionResponse | None)
async def get_ticket_routing_decision(
    ticket_id: uuid.UUID,
    service: TicketQuerySvc,
) -> RoutingDecisionResponse | None:
    decision = await service.get_latest_routing_decision(ticket_id)
    if decision is None:
        return None
    data = RoutingDecisionResponse.model_validate(decision)
    return data.model_copy(
        update={"human_review_required": decision.reason == "human_review_required"}
    )


@router.get(
    "/{ticket_id}/draft-suggestion",
    response_model=DraftSuggestionResponse | None,
)
async def get_ticket_draft_suggestion(
    ticket_id: uuid.UUID,
    service: TicketQuerySvc,
) -> DraftSuggestionResponse | None:
    draft = await service.get_latest_draft_suggestion(ticket_id)
    if draft is None:
        return None
    return DraftSuggestionResponse.model_validate(draft)


@router.post(
    "/{ticket_id}/embeddings/test",
    response_model=TicketEmbeddingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store test embedding (local scaffolding only)",
    description=(
        "Persists a caller-provided vector for local testing. "
        "Does not generate embeddings or call AI providers."
    ),
)
async def store_test_embedding(
    ticket_id: uuid.UUID,
    body: StoreTestEmbeddingRequest,
    service: EmbeddingPersistenceSvc,
) -> TicketEmbeddingResponse:
    row = await service.store_ticket_embedding(
        ticket_id,
        embedding=body.embedding,
        embedding_model=body.embedding_model or DEFAULT_EMBEDDING_MODEL,
        embedding_dimension=body.embedding_dimension or EMBEDDING_DIMENSION,
        source_text_hash=body.source_text_hash,
    )
    return TicketEmbeddingResponse.model_validate(row)
