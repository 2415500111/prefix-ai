"""Per-request metadata that the audit log needs (request id, client IP, user agent).

Stored as a mutable object in a ContextVar so that code running in the threadpool
(sync dependencies and endpoints) and the middleware share the same instance.
"""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class RequestContext:
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    touches_patient_data: bool = False
    audit_records_written: int = 0


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(context: RequestContext) -> None:
    _current.set(context)


def current_request_context() -> RequestContext | None:
    return _current.get()
