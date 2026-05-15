from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthRepository:
    """Authoritative store connectivity (repositories own SQL execution)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping_postgres(self) -> None:
        await self._session.execute(text("SELECT 1"))
