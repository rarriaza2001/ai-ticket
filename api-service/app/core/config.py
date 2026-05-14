from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueueBackend(StrEnum):
    """Reserved queue implementation selector (Phase 2: SQS, Redis Stream, etc.)."""

    UNSET = "unset"
    SQS = "sqs"
    REDIS_STREAM = "redis_stream"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="api-service", validation_alias="SERVICE_NAME")
    env: str = Field(default="local", validation_alias="ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(
        ...,
        validation_alias="DATABASE_URL",
        description="asyncpg DSN, e.g. postgresql://user:pass@host:5432/db",
    )
    db_pool_max_size: int = Field(default=10, validation_alias="DB_POOL_MAX_SIZE")
    db_command_timeout_seconds: int = Field(
        default=60,
        validation_alias="DB_COMMAND_TIMEOUT_SECONDS",
    )

    redis_url: str = Field(..., validation_alias="REDIS_URL")
    redis_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="REDIS_CONNECT_TIMEOUT_SECONDS"
    )
    redis_socket_timeout_seconds: float = Field(
        default=5.0, validation_alias="REDIS_SOCKET_TIMEOUT_SECONDS"
    )

    queue_backend: QueueBackend = Field(
        default=QueueBackend.UNSET,
        validation_alias="QUEUE_BACKEND",
    )

    # Phase 2 — do not require in Phase 1
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @property
    def sqlalchemy_sync_url(self) -> str:
        """Alembic / sync SQLAlchemy URL (psycopg v3)."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
