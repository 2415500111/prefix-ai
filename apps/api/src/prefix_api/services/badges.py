"""Counts for the staff sidebar: open tasks, open escalations, pending reschedule requests.

Only totals leave this service, never a patient, so reading them is not a patient-data read.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.db.models import Escalation, Task
from prefix_api.domain.enums import EscalationStatus, TaskStatus, TaskType
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal

_OPEN = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)


@dataclass(frozen=True, slots=True)
class Badges:
    open_tasks: int
    open_escalations: int
    pending_requests: int


class BadgeService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def counts(self, principal: StaffPrincipal) -> Badges:
        principal.require(Permission.APPOINTMENT_READ)
        organization = principal.organization_id
        tasks = self._session.scalar(
            select(func.count()).where(
                Task.organization_id == organization,
                Task.status.in_(_OPEN),
                Task.type != TaskType.RESCHEDULE,
            )
        )
        requests = self._session.scalar(
            select(func.count()).where(
                Task.organization_id == organization,
                Task.status.in_(_OPEN),
                Task.type == TaskType.RESCHEDULE,
            )
        )
        escalations = self._session.scalar(
            select(func.count()).where(
                Escalation.organization_id == organization,
                Escalation.status != EscalationStatus.RESOLVED,
            )
        )
        return Badges(
            open_tasks=tasks or 0,
            open_escalations=escalations or 0,
            pending_requests=requests or 0,
        )
