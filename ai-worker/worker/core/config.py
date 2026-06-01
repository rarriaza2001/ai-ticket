from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="ai-worker", validation_alias="SERVICE_NAME")
    env: str = Field(default="local", validation_alias="ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(..., validation_alias="DATABASE_URL")

    redis_url: str = Field(..., validation_alias="REDIS_URL")
    redis_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="REDIS_CONNECT_TIMEOUT_SECONDS"
    )
    redis_socket_timeout_seconds: float = Field(
        default=5.0, validation_alias="REDIS_SOCKET_TIMEOUT_SECONDS"
    )

    cache_enabled: bool = Field(default=True, validation_alias="CACHE_ENABLED")
    cache_delete_invalid_on_read: bool = Field(
        default=True, validation_alias="CACHE_DELETE_INVALID_ON_READ"
    )

    ai_provider: str = Field(default="mock", validation_alias="AI_PROVIDER")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    openai_embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_embedding_dimension: int = Field(
        default=1536, validation_alias="OPENAI_EMBEDDING_DIMENSION"
    )
    openai_classification_model: str = Field(
        default="gpt-4.1-mini", validation_alias="OPENAI_CLASSIFICATION_MODEL"
    )
    openai_suggestion_model: str = Field(
        default="gpt-4.1-mini", validation_alias="OPENAI_SUGGESTION_MODEL"
    )

    retrieval_top_k: int = Field(default=5, validation_alias="RETRIEVAL_TOP_K")
    retrieval_usable_max_distance: float = Field(
        default=0.30, validation_alias="RETRIEVAL_USABLE_MAX_DISTANCE"
    )
    retrieval_context_max_age_days: int = Field(
        default=180, validation_alias="RETRIEVAL_CONTEXT_MAX_AGE_DAYS"
    )

    classification_confidence_high: float = Field(
        default=0.80, validation_alias="CLASSIFICATION_CONFIDENCE_HIGH"
    )
    classification_confidence_medium: float = Field(
        default=0.60, validation_alias="CLASSIFICATION_CONFIDENCE_MEDIUM"
    )
    routing_confidence_min: float = Field(
        default=0.80, validation_alias="ROUTING_CONFIDENCE_MIN"
    )

    embedding_max_retries: int = Field(default=3, validation_alias="EMBEDDING_MAX_RETRIES")
    classification_max_retries: int = Field(
        default=2, validation_alias="CLASSIFICATION_MAX_RETRIES"
    )
    suggestion_max_retries: int = Field(default=2, validation_alias="SUGGESTION_MAX_RETRIES")

    force_regenerate_embeddings: bool = Field(
        default=False, validation_alias="FORCE_REGENERATE_EMBEDDINGS"
    )

    worker_poll_interval_seconds: float = Field(
        default=5.0, validation_alias="WORKER_POLL_INTERVAL_SECONDS"
    )
    worker_batch_size: int = Field(default=10, validation_alias="WORKER_BATCH_SIZE")

    @property
    def sqlalchemy_async_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    def validate_openai_config(self) -> None:
        if self.ai_provider.strip().lower() == "openai" and not (self.openai_api_key or "").strip():
            msg = (
                "AI_PROVIDER=openai requires OPENAI_API_KEY in environment. "
                "Use AI_PROVIDER=mock for local tests."
            )
            raise ValueError(msg)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
