"""Central API error types and FastAPI exception handler registration."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class PostgresUnavailable(Exception):
    """Postgres dependency unreachable during readiness evaluation."""

    def __init__(self, *, redis_ok: bool = False) -> None:
        super().__init__("Postgres unreachable")
        self.redis_ok = redis_ok


class TicketNotFound(Exception):
    """Ticket does not exist."""

    def __init__(self, ticket_id: object) -> None:
        super().__init__(f"Ticket not found: {ticket_id}")
        self.ticket_id = ticket_id


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TicketNotFound)
    async def ticket_not_found_handler(
        request: Request,
        exc: TicketNotFound,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "code": "ticket_not_found",
                "message": str(exc),
                "ticket_id": str(exc.ticket_id),
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(PostgresUnavailable)
    async def postgres_unavailable_handler(
        request: Request,
        exc: PostgresUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=jsonable_encoder(
                {
                    "code": "postgres_unavailable",
                    "message": str(exc),
                    "postgres": False,
                    "redis": exc.redis_ok,
                    "degraded": False,
                    "request_id": _request_id(request),
                }
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail
        if not isinstance(detail, str):
            detail = jsonable_encoder(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": "http_error",
                "message": detail,
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request validation failed",
                "errors": jsonable_encoder(exc.errors()),
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled.error", request_id=_request_id(request))
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "An unexpected error occurred",
                "request_id": _request_id(request),
            },
        )
