from __future__ import annotations

import pytest

from worker.core.config import get_settings
from worker.providers.factory import create_ai_provider


def test_openai_without_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://ticket:ticket@localhost:5433/tickets")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        settings.validate_openai_config()


def test_mock_provider_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    settings = get_settings()
    provider = create_ai_provider(settings)
    assert provider.provider_name == "mock"
