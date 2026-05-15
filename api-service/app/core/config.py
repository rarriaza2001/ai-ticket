from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="api-service", validation_alias="SERVICE_NAME")
    env: str = Field(default="local", validation_alias="ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    database_url: str = Field(
        ...,
        validation_alias="DATABASE_URL",
        description="Postgres DSN, e.g. postgresql://user:pass@postgres:5432/db",
    )
    db_pool_size: int = Field(default=5, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT_SECONDS")

    redis_url: str = Field(..., validation_alias="REDIS_URL")
    redis_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="REDIS_CONNECT_TIMEOUT_SECONDS"
    )
    redis_socket_timeout_seconds: float = Field(
        default=5.0, validation_alias="REDIS_SOCKET_TIMEOUT_SECONDS"
    )

    @property
    def sqlalchemy_async_url(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver)."""
        url = self.database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sqlalchemy_sync_url(self) -> str:
        """Alembic / sync SQLAlchemy URL (psycopg v3)."""
        url = self.database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
