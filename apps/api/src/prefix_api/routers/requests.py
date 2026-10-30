"""Reschedule requests from patients: the list, and the care team's answer."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.operations import TaskOut
from prefix_api.schemas.requests import ApproveRequest, RequestOut
from prefix_api.services.requests import RequestItem, RequestService

router = APIRouter(
    prefix="/requests", tags=["requests"], dependencies=[Depends(patient_data_route)]
)

Reader = Annotated[StaffPrincipal, Depends(require(Permission.TASK_MANAGE))]
Writer = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_WRITE))]


def _out(item: RequestItem) -> RequestOut:
    return RequestOut(
        id=item.task.id,
        appointment_id=item.appointment.id,
        patient_id=item.appointment.patient_id,
        patient_name=item.patient_name,
        procedure_name=item.procedure_name,
        scheduled_at=item.appointment.scheduled_at,
        status=item.status,
        created_at=item.task.created_at,
        decided_at=item.task.completed_at,
    )


@router.get("")
def list_requests(principal: Reader, session: DbSession, now: Now) -> list[RequestOut]:
    return [_out(item) for item in RequestService(session).overview(principal, now=now)]


@router.post("/{task_id}/approve")
def approve_request(
    task_id: uuid.UUID, body: ApproveRequest, principal: Writer, session: DbSession, now: Now
) -> TaskOut:
    task = RequestService(session).approve(principal, task_id, body.scheduled_at, now=now)
    return TaskOut.model_validate(task)


@router.post("/{task_id}/decline")
def decline_request(task_id: uuid.UUID, principal: Writer, session: DbSession, now: Now) -> TaskOut:
    return TaskOut.model_validate(RequestService(session).decline(principal, task_id, now=now))
