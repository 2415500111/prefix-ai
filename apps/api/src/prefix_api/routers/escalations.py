"""Nurse inbox: escalations from red flags, patient-reported problems and the assistant."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.escalations import EscalationOut, EscalationResolve
from prefix_api.services.escalations import EscalationService

router = APIRouter(
    prefix="/escalations", tags=["escalations"], dependencies=[Depends(patient_data_route)]
)

Handler = Annotated[StaffPrincipal, Depends(require(Permission.ESCALATION_HANDLE))]


@router.get("")
def list_escalations(
    principal: Handler,
    session: DbSession,
    now: Now,
    status: Literal["open", "resolved", "all"] = "open",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[EscalationOut]:
    """Newest first by when it was raised; urgency is shown, never sorted on."""
    items = EscalationService(session).inbox(principal, now=now, status=status, limit=limit)
    return [EscalationOut.from_item(item) for item in items]


@router.post("/{escalation_id}/acknowledge")
def acknowledge_escalation(
    escalation_id: uuid.UUID, principal: Handler, session: DbSession, now: Now
) -> EscalationOut:
    service = EscalationService(session)
    service.acknowledge(principal, escalation_id, now=now)
    return EscalationOut.from_item(service.item(principal, escalation_id, now=now))


@router.post("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: uuid.UUID,
    body: EscalationResolve,
    principal: Handler,
    session: DbSession,
    now: Now,
) -> EscalationOut:
    service = EscalationService(session)
    service.resolve(principal, escalation_id, note=body.note, now=now)
    return EscalationOut.from_item(service.item(principal, escalation_id, now=now))
