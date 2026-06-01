import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.cache.redis_cache_store import get_last_cache_result, reset_last_cache_result


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propagate `X-Request-ID` (or generate) for correlation with logs (Phase 2 tracing)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        reset_last_cache_result(request)
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            cache_result = get_last_cache_result(request)
            if cache_result is not None:
                response.headers["X-Cache-Hit"] = "1" if cache_result else "0"
            return response
        finally:
            structlog.contextvars.clear_contextvars()
