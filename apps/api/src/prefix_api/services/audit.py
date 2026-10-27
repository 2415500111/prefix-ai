"""Audit logging (safety rule d). Services call `record_audit` for every read or write of
patient data, in the same transaction as the change it describes."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from prefix_api.core.request_context import current_request_context
from prefix_api.db.models import AuditLog
from prefix_api.domain.enums import ActorType, AuditAction
from prefix_api.domain.principal import Principal

# Keys allowed in `details`. Anything else is dropped so PHI cannot leak into audit rows.
_ALLOWED_DETAIL_KEYS = frozenset(
    {"fields", "count", "reason", "role", "query", "status", "target_role", "family_id"}
)


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    return {key: value for key, value in details.items() if key in _ALLOWED_DETAIL_KEYS}


def record_audit(
    session: Session,
    *,
    principal: Principal | None,
    action: AuditAction,
    entity_type: str,
    purpose: str,
    entity_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    context = current_request_context()
    entry = AuditLog(
        organization_id=organization_id
        or (principal.organization_id if principal is not None else None),
        actor_type=principal.actor_type if principal is not None else ActorType.ANONYMOUS,
        actor_id=principal.actor_id if principal is not None else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        patient_id=patient_id,
        purpose=purpose,
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent[:300] if context and context.user_agent else None,
        request_id=context.request_id if context else None,
        details=_safe_details(details),
    )
    session.add(entry)
    if context is not None:
        context.audit_records_written += 1
