from __future__ import annotations

from worker.core.config import Settings
from worker.providers.base import AiProvider
from worker.providers.mock_provider import MockAiProvider
from worker.providers.openai_provider import OpenAiProvider


def create_ai_provider(settings: Settings, *, mock_overrides: dict | None = None) -> AiProvider:
    provider = settings.ai_provider.strip().lower()
    if provider == "mock":
        overrides = mock_overrides or {}
        return MockAiProvider(**overrides)
    if provider == "openai":
        settings.validate_openai_config()
        return OpenAiProvider(settings)
    raise ValueError(f"Unknown AI_PROVIDER: {settings.ai_provider}")
