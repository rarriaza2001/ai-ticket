"""Structured AI classification and suggestion metadata DTOs."""

from pydantic import BaseModel, ConfigDict, Field


class ClassificationOutput(BaseModel):
    """Structured classification response from AI providers."""

    model_config = ConfigDict(extra="forbid")

    category: str
    team: str
    priority: str
    classification_confidence: float = Field(ge=0.0, le=1.0)
    routing_confidence: float = Field(ge=0.0, le=1.0)
    escalation: str = "none"


class SuggestionMetadata(BaseModel):
    """Optional structured metadata for draft suggestions (not the draft body)."""

    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
