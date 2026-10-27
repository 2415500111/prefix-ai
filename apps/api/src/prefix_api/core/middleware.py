import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

from prefix_api.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 128

logger = get_logger(__name__)


def _request_id_from(request: Request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    if incoming and len(incoming) <= _MAX_REQUEST_ID_LENGTH and incoming.isprintable():
        return incoming
    return uuid.uuid4().hex


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Bind a request id to every log line and emit one access log per request.

    The query string is deliberately not logged: it may carry patient identifiers.
    """
    request_id = _request_id_from(request)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request.failed",
            method=request.method,
            path=request.url.path,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise

    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request.completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response
