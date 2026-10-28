"""Tasks: a person closes a piece of work that the system opened."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.operations import TaskOut
from prefix_api.services.tasks import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(patient_data_route)])

Completer = Annotated[StaffPrincipal, Depends(require(Permission.TASK_COMPLETE))]


@router.post("/{task_id}/complete")
def complete_task(
    task_id: uuid.UUID, principal: Completer, session: DbSession, now: Now
) -> TaskOut:
    return TaskOut.model_validate(TaskService(session).complete(principal, task_id, now=now))
