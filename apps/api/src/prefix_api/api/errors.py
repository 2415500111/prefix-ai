from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
