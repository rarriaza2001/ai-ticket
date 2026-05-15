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

    @property
    def sqlalchemy_async_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
