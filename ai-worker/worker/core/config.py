from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueueBackend(StrEnum):
    """Reserved queue implementation selector (Phase 2)."""

    UNSET = "unset"
    SQS = "sqs"
    REDIS_STREAM = "redis_stream"


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
    db_pool_max_size: int = Field(default=4, validation_alias="DB_POOL_MAX_SIZE")
    db_command_timeout_seconds: int = Field(default=120, validation_alias="DB_COMMAND_TIMEOUT_SECONDS")

    redis_url: str = Field(..., validation_alias="REDIS_URL")
    redis_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="REDIS_CONNECT_TIMEOUT_SECONDS"
    )
    redis_socket_timeout_seconds: float = Field(
        default=5.0, validation_alias="REDIS_SOCKET_TIMEOUT_SECONDS"
    )

    queue_backend: QueueBackend = Field(default=QueueBackend.UNSET, validation_alias="QUEUE_BACKEND")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
