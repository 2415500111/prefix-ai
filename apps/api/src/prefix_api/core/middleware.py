import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from prefix_api.core.logging import get_logger
from prefix_api.core.request_context import (
    RequestContext,
    current_request_context,
    set_request_context,
)
from prefix_api.domain.enums import ActorType, AuditAction

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 128

type CallNext = Callable[[Request], Awaitable[Response]]

logger = get_logger(__name__)


def _request_id_from(request: Request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    if incoming and len(incoming) <= _MAX_REQUEST_ID_LENGTH and incoming.isprintable():
        return incoming
    return uuid.uuid4().hex


async def request_context_middleware(request: Request, call_next: CallNext) -> Response:
    """Bind a request id to every log line, collect audit metadata, and emit one access log.

    The query string is deliberately not logged: it may carry patient identifiers.
    """
    request_id = _request_id_from(request)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    set_request_context(
        RequestContext(
            request_id=request_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )

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


def _write_backstop_audit(request: Request, context: RequestContext) -> None:
    # Imported lazily: middleware must not import the ORM layer at module import time.
    from prefix_api.db.models import AuditLog

    session = request.app.state.session_factory()
    try:
        session.add(
            AuditLog(
                actor_type=ActorType.ANONYMOUS,
                action=AuditAction.READ if request.method == "GET" else AuditAction.UPDATE,
                entity_type="http_request",
                purpose="audit_backstop",
                ip_address=context.ip_address,
                user_agent=context.user_agent[:300] if context.user_agent else None,
                request_id=context.request_id,
                details={"reason": "route_wrote_no_audit_record"},
            )
        )
        session.commit()
    finally:
        session.close()


async def audit_backstop_middleware(request: Request, call_next: CallNext) -> Response:
    """Safety net for safety rule (d): if a route marked as handling patient data succeeds
    without writing any audit record, log an error and write a generic audit entry."""
    response = await call_next(request)
    context = current_request_context()
    if (
        context is not None
        and context.touches_patient_data
        and context.audit_records_written == 0
        and response.status_code < 400
    ):
        logger.error("audit.missing", method=request.method, path=request.url.path)
        await run_in_threadpool(_write_backstop_audit, request, context)
    return response
