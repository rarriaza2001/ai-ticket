from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from shared_contracts import (
    ClassificationOutput,
    SuggestionMetadata,
    SupportTeam,
    TicketCategory,
    TicketPriority,
)
from worker.core.config import Settings
from worker.providers.base import (
    AiProvider,
    ClassificationResult,
    DraftSuggestionResult,
    EmbeddingResult,
)
from worker.providers.errors import MalformedModelOutput


def _validate_taxonomy(output: ClassificationOutput) -> ClassificationOutput:
    try:
        TicketCategory(output.category)
        SupportTeam(output.team)
        TicketPriority(output.priority)
    except ValueError as exc:
        raise MalformedModelOutput(str(exc)) from exc
    return output


class OpenAiProvider(AiProvider):
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAiProvider")
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed_text(self, text: str) -> EmbeddingResult:
        response = await self._client.embeddings.create(
            model=self._settings.openai_embedding_model,
            input=text,
            dimensions=self._settings.openai_embedding_dimension,
        )
        vector = list(response.data[0].embedding)
        return EmbeddingResult(
            vector=vector,
            model_name=self._settings.openai_embedding_model,
            provider_name=self.provider_name,
            embedding_dimension=self._settings.openai_embedding_dimension,
        )

    async def classify(self, *, subject: str, body: str, prompt: str) -> ClassificationResult:
        user_content = (
            f"{prompt}\n\n"
            f"Subject: {subject}\n"
            f"Body: {body}\n"
            "Respond with JSON matching the classification schema."
        )
        response = await self._client.chat.completions.create(
            model=self._settings.openai_classification_model,
            messages=[
                {
                    "role": "system",
                    "content": "You classify support tickets. Output valid JSON only.",
                },
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw_text = response.choices[0].message.content or ""
        try:
            data: dict[str, Any] = json.loads(raw_text)
            parsed = _validate_taxonomy(ClassificationOutput.model_validate(data))
        except (json.JSONDecodeError, ValidationError, MalformedModelOutput) as exc:
            raise MalformedModelOutput(str(exc)) from exc

        return ClassificationResult(
            category=parsed.category,
            team=parsed.team,
            priority=parsed.priority,
            escalation=parsed.escalation,
            classification_confidence=parsed.classification_confidence,
            routing_confidence=parsed.routing_confidence,
            raw=data,
        )

    async def generate_draft_suggestion(
        self,
        *,
        subject: str,
        body: str,
        similar_subjects: list[str],
        similar_ticket_ids: list[str],
        prompt: str,
    ) -> DraftSuggestionResult:
        context_lines = [
            f"- {tid}: {subj}" for tid, subj in zip(similar_ticket_ids, similar_subjects, strict=False)
        ]
        context_block = "\n".join(context_lines) if context_lines else "(none)"
        user_content = (
            f"{prompt}\n\n"
            f"Current ticket subject: {subject}\n"
            f"Similar tickets:\n{context_block}\n"
            "Produce a draft reply for human review only. "
            "Respond with JSON: {\"draft_text\": string, \"summary\": string|null, "
            "\"key_points\": string[]}"
        )
        response = await self._client.chat.completions.create(
            model=self._settings.openai_suggestion_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You draft support replies for human review. Never imply auto-send."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw_text = response.choices[0].message.content or ""
        try:
            data = json.loads(raw_text)
            draft_text = str(data.get("draft_text", "")).strip()
            if not draft_text:
                raise MalformedModelOutput("empty draft_text")
            metadata = SuggestionMetadata(
                summary=data.get("summary"),
                key_points=list(data.get("key_points") or []),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise MalformedModelOutput(str(exc)) from exc

        return DraftSuggestionResult(
            draft_text=draft_text,
            confidence=0.75,
            model_name=self._settings.openai_suggestion_model,
            provider_name=self.provider_name,
            metadata=metadata,
        )
