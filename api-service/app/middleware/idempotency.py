from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Capture `Idempotency-Key` for POST /tickets (dedupe logic lands in Phase 2)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.idempotency_key = request.headers.get("Idempotency-Key")
        response: Response = await call_next(request)
        return response
