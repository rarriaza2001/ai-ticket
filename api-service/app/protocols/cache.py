from typing import Any, Protocol


class TicketCacheProtocol(Protocol):
    """Ephemeral cache for ticket-shaped JSON; invalidation is explicit in Phase 2."""

    async def get_json(self, key: str) -> dict[str, Any] | None:
        ...

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int | None) -> None:
        ...

    async def invalidate(self, key: str) -> None:
        ...
