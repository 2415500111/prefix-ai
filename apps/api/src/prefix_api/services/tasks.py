"""Coordinator and nurse tasks: work to be done for a patient, closed by a person."""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Task
from prefix_api.domain.enums import AuditAction, TaskStatus
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.services.audit import record_audit

PURPOSE = "task_completion"


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def complete(self, principal: StaffPrincipal, task_id: uuid.UUID, *, now: dt.datetime) -> Task:
        principal.require(Permission.TASK_COMPLETE)
        task = self._session.scalar(
            select(Task)
            .where(Task.id == task_id, Task.organization_id == principal.organization_id)
            .with_for_update()
        )
        if task is None:
            raise NotFoundError("Task not found")
        if task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            raise ConflictError(f"This task is already {task.status.value.lower()}")
        task.status = TaskStatus.DONE
        task.completed_at = now
        task.assignee_id = task.assignee_id or principal.user_id
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.UPDATE,
            entity_type="task",
            entity_id=task.id,
            patient_id=task.patient_id,
            purpose=PURPOSE,
            details={"status": TaskStatus.DONE.value},
        )
        return task
