from __future__ import annotations

import re
from dataclasses import dataclass

_MAX_TEXT_LENGTH = 8000
_EXCERPT_LENGTH = 200

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?!\d)"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class PreparedText:
    subject: str
    body: str
    sanitized_text: str


def _normalize_segment(text: str) -> str:
    collapsed = _WHITESPACE_PATTERN.sub(" ", text.strip())
    return collapsed


def _mask_pii(text: str) -> str:
    masked = _EMAIL_PATTERN.sub("[EMAIL]", text)
    return _PHONE_PATTERN.sub("[PHONE]", masked)


def _truncate(text: str, *, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def prepare_ticket_text(subject: str, body: str) -> PreparedText:
    """Normalize, lightly mask PII, and build a single text block for AI steps."""
    normalized_subject = _normalize_segment(subject)
    normalized_body = _normalize_segment(body)
    combined = f"{normalized_subject}\n{normalized_body}".strip()
    masked = _mask_pii(combined)
    sanitized = _truncate(masked, max_length=_MAX_TEXT_LENGTH)
    return PreparedText(
        subject=normalized_subject,
        body=normalized_body,
        sanitized_text=sanitized,
    )


def excerpt_body(body: str, *, max_length: int = _EXCERPT_LENGTH) -> str:
    """Short sanitized excerpt for retrieval context (no full ticket dump)."""
    normalized = _normalize_segment(body)
    masked = _mask_pii(normalized)
    return _truncate(masked, max_length=max_length)
