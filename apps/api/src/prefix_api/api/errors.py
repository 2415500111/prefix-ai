from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from prefix_api.core.logging import get_logger
from prefix_api.db.session import database_location
from prefix_api.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)

_STATUS: dict[type[DomainError], int] = {
    NotFoundError: 404,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    ConflictError: 409,
    ValidationFailedError: 422,
}

# Internal detail (e.g. which permission a role lacks) stays in logs, not responses.
_PUBLIC_MESSAGE: dict[type[DomainError], str] = {
    PermissionDeniedError: "You do not have permission to do this",
}


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)  # noqa: S101 - registered for DomainError only
    status = next((code for cls, code in _STATUS.items() if isinstance(exc, cls)), 400)
    message = _PUBLIC_MESSAGE.get(type(exc), exc.message)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(
        status_code=status, content={"detail": message, "code": exc.code}, headers=headers
    )


logger = get_logger(__name__)


async def _handle_database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    """A query failed because the database cannot be reached: say so, and fail the request now."""
    bind = request.app.state.session_factory.kw.get("bind")
    where = database_location(bind) if isinstance(bind, Engine) else "unknown host"
    logger.error(f"Database not reachable at {where}", error=type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The database is unavailable right now. Please try again shortly.",
            "code": "database_unavailable",
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(OperationalError, _handle_database_unreachable)
