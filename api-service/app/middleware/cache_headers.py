"""Expose last cache hit/miss on responses for benchmarks (no cached body in header)."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.cache.redis_cache_store import get_last_cache_result, reset_last_cache_result


class CacheHeadersMiddleware:
    """Pure ASGI middleware so contextvars from cache reads propagate to response headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        reset_last_cache_result()

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                result = get_last_cache_result()
                if result is not None:
                    headers = list(message.get("headers", []))
                    headers.append((b"x-cache-hit", b"1" if result else b"0"))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def apply_cache_headers_middleware(app: ASGIApp) -> ASGIApp:
    """Register cache header middleware (use instead of add_middleware(BaseHTTPMiddleware))."""
    return CacheHeadersMiddleware(app)
