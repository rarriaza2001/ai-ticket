from enum import StrEnum


class TicketStatus(StrEnum):
    RECEIVED = "received"
    PENDING_EMBEDDING = "pending_embedding"
    EMBEDDED = "embedded"
    ROUTING_PENDING = "routing_pending"
    ROUTED = "routed"
    FAILED = "failed"


class RoutingDecisionType(StrEnum):
    CATEGORY = "category"
    TEAM = "team"
    PRIORITY = "priority"
    ESCALATION = "escalation"


class DecidedBy(StrEnum):
    WORKER = "worker"
    MANUAL = "manual"
    TEST_SEED = "test_seed"


class TicketEventType(StrEnum):
    TICKET_RECEIVED = "ticket_received"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    EMBEDDING_STORED = "embedding_stored"
    ROUTING_DECISION_STORED = "routing_decision_stored"
    TICKET_FAILED = "ticket_failed"
    AI_PROCESSING_STARTED = "ai_processing_started"
    CLASSIFICATION_COMPLETED = "classification_completed"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    DRAFT_SUGGESTION_STORED = "draft_suggestion_stored"
    AI_PROCESSING_COMPLETED = "ai_processing_completed"
    AI_PROCESSING_FAILED = "ai_processing_failed"
