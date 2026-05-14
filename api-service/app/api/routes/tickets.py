from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from shared_contracts import (
    RoutingDecision,
    SimilarTicketSnapshot,
    Ticket,
    TicketCreateRequest,
    TicketSuggestion,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

_NOT_IMPLEMENTED = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={"code": "NOT_IMPLEMENTED", "phase": 1},
)


@router.post(
    "",
    summary="Create ticket",
    description=(
        "Intake endpoint (Phase 2). Optional `Idempotency-Key` header will be honored for dedupe; "
        "middleware stores it on `request.state.idempotency_key`."
    ),
    response_model=None,
)
async def create_ticket(_body: TicketCreateRequest, _request: Request) -> Ticket:
    raise _NOT_IMPLEMENTED


@router.get("/{ticket_id}", response_model=None)
async def get_ticket(ticket_id: UUID) -> Ticket:
    _ = ticket_id
    raise _NOT_IMPLEMENTED


@router.get("/{ticket_id}/routing", response_model=None)
async def get_routing(ticket_id: UUID) -> RoutingDecision:
    _ = ticket_id
    raise _NOT_IMPLEMENTED


@router.get("/{ticket_id}/suggestion", response_model=None)
async def get_suggestion(ticket_id: UUID) -> TicketSuggestion:
    _ = ticket_id
    raise _NOT_IMPLEMENTED


@router.get("/{ticket_id}/similar", response_model=None)
async def get_similar(ticket_id: UUID) -> SimilarTicketSnapshot:
    _ = ticket_id
    raise _NOT_IMPLEMENTED


@router.post("/{ticket_id}/reprocess", response_model=None)
async def reprocess_ticket(ticket_id: UUID) -> Ticket:
    _ = ticket_id
    raise _NOT_IMPLEMENTED
