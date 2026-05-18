from enum import StrEnum


class TicketStatus(StrEnum):
    RECEIVED = "received"
    PENDING_EMBEDDING = "pending_embedding"
    EMBEDDED = "embedded"
    ROUTING_PENDING = "routing_pending"
    ROUTED = "routed"
    FAILED = "failed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RoutingDecisionType(StrEnum):
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
