from __future__ import annotations

from dataclasses import dataclass

from shared_contracts import SupportTeam, TicketCategory, TicketPriority
from worker.providers.base import ClassificationResult
from worker.providers.errors import MalformedModelOutput


@dataclass(frozen=True)
class ParsedClassification:
    category: str
    team: str
    priority: str
    escalation: str
    classification_confidence: float
    routing_confidence: float
    requires_human_review: bool
    fallback_reason: str | None


def apply_classification_policy(
    raw: ClassificationResult,
    *,
    confidence_high: float,
    confidence_medium: float,
    routing_confidence_min: float,
) -> ParsedClassification:
    category = raw.category
    team = raw.team
    priority = raw.priority
    escalation = raw.escalation or "none"
    classification_confidence = raw.classification_confidence
    routing_confidence = raw.routing_confidence
    requires_human_review = False
    fallback_reason: str | None = None

    if classification_confidence < confidence_medium:
        category = TicketCategory.UNKNOWN.value
        team = SupportTeam.TRIAGE.value
        priority = TicketPriority.NORMAL.value
        requires_human_review = True
        fallback_reason = "low_classification_confidence"
    elif classification_confidence < confidence_high:
        requires_human_review = True

    if routing_confidence < routing_confidence_min:
        team = SupportTeam.TRIAGE.value
        requires_human_review = True
        fallback_reason = fallback_reason or "low_routing_confidence"

    return ParsedClassification(
        category=category,
        team=team,
        priority=priority,
        escalation=escalation,
        classification_confidence=classification_confidence,
        routing_confidence=routing_confidence,
        requires_human_review=requires_human_review,
        fallback_reason=fallback_reason,
    )


def fallback_classification(*, reason: str) -> ParsedClassification:
    return ParsedClassification(
        category=TicketCategory.UNKNOWN.value,
        team=SupportTeam.TRIAGE.value,
        priority=TicketPriority.NORMAL.value,
        escalation="none",
        classification_confidence=0.0,
        routing_confidence=0.0,
        requires_human_review=True,
        fallback_reason=reason,
    )


def validate_raw_classification(raw: ClassificationResult) -> ClassificationResult:
    try:
        TicketCategory(raw.category)
        SupportTeam(raw.team)
        TicketPriority(raw.priority)
    except ValueError as exc:
        raise MalformedModelOutput(str(exc)) from exc
    return raw
