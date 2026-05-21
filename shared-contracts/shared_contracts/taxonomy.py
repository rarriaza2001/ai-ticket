"""Support ticket taxonomy enums shared across services."""

from enum import StrEnum


class TicketCategory(StrEnum):
    BILLING = "billing"
    ACCOUNT_ACCESS = "account_access"
    TECHNICAL_ISSUE = "technical_issue"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    SECURITY = "security"
    GENERAL_SUPPORT = "general_support"
    UNKNOWN = "unknown"


class SupportTeam(StrEnum):
    TRIAGE = "triage"
    BILLING_SUPPORT = "billing_support"
    TECHNICAL_SUPPORT = "technical_support"
    ACCOUNT_SUPPORT = "account_support"
    SECURITY_REVIEW = "security_review"
    CUSTOMER_SUCCESS = "customer_success"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
