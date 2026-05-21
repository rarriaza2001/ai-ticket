from __future__ import annotations

from worker.services.text_preparation import excerpt_body, prepare_ticket_text


def test_prepare_collapses_whitespace() -> None:
    prepared = prepare_ticket_text("  Billing   issue  ", "Line one.\n\nLine two.")
    assert prepared.subject == "Billing issue"
    assert prepared.body == "Line one. Line two."
    assert "Billing issue" in prepared.sanitized_text
    assert "\n\n" not in prepared.sanitized_text


def test_prepare_masks_email_and_phone() -> None:
    prepared = prepare_ticket_text(
        "Contact me",
        "Email user@example.com or call +1 555-123-4567 today.",
    )
    assert "[EMAIL]" in prepared.sanitized_text
    assert "[PHONE]" in prepared.sanitized_text
    assert "user@example.com" not in prepared.sanitized_text


def test_prepare_truncates_long_text() -> None:
    long_body = "word " * 3000
    prepared = prepare_ticket_text("Subj", long_body)
    assert len(prepared.sanitized_text) <= 8000
    assert prepared.sanitized_text.endswith("...")


def test_excerpt_body_limits_length() -> None:
    excerpt = excerpt_body("x" * 500, max_length=50)
    assert len(excerpt) <= 50
    assert excerpt.endswith("...")
