"""The nurse inbox: escalations that need a person, most urgent first."""

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy import Row, Select, case, select, update
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, Escalation, Patient, ProcedureType, Task
from prefix_api.domain.enums import (
    AuditAction,
    EscalationSeverity,
    EscalationStatus,
    TaskStatus,
)
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.services.audit import record_audit

InboxFilter = Literal["open", "resolved", "all"]
PURPOSE = "escalation_handling"
_STATUSES: dict[InboxFilter, tuple[EscalationStatus, ...]] = {
    "open": (EscalationStatus.OPEN, EscalationStatus.ACKNOWLEDGED),
    "resolved": (EscalationStatus.RESOLVED,),
    "all": tuple(EscalationStatus),
}
_SEVERITY_RANK = case(
    (Escalation.severity == EscalationSeverity.URGENT, 0),
    (Escalation.severity == EscalationSeverity.HIGH, 1),
    else_=2,
)


def _to_item(row: Row[Escalation, Patient, Appointment | None, str | None]) -> InboxItem:
    """Read the joined columns by position; mypy cannot unpack a Row of this query."""
    escalation: Escalation = row[0]
    patient: Patient = row[1]
    appointment: Appointment | None = row[2]
    procedure_name: str | None = row[3]
    return InboxItem(escalation, patient, appointment, procedure_name)


@dataclass(frozen=True, slots=True)
class InboxItem:
    escalation: Escalation
    patient: Patient
    appointment: Appointment | None
    procedure_name: str | None


class EscalationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def inbox(
        self, principal: StaffPrincipal, *, status: InboxFilter = "open", limit: int = 100
    ) -> list[InboxItem]:
        principal.require(Permission.ESCALATION_HANDLE)
        rows = self._session.execute(
            self._query(principal.organization_id)
            .where(Escalation.status.in_(_STATUSES[status]))
            .order_by(_SEVERITY_RANK, Escalation.created_at)
            .limit(limit)
        ).all()
        items = []
        for row in rows:
            item = _to_item(row)
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.LIST,
                entity_type="escalation",
                entity_id=item.escalation.id,
                patient_id=item.patient.id,
                purpose=PURPOSE,
            )
            items.append(item)
        return items

    def item(self, principal: StaffPrincipal, escalation_id: uuid.UUID) -> InboxItem:
        """One escalation in the same shape as the inbox (used after changing it)."""
        principal.require(Permission.ESCALATION_HANDLE)
        row = self._session.execute(
            self._query(principal.organization_id).where(Escalation.id == escalation_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("Escalation not found")
        item = _to_item(row)
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="escalation",
            entity_id=item.escalation.id,
            patient_id=item.patient.id,
            purpose=PURPOSE,
        )
        return item

    def _query(
        self, organization_id: uuid.UUID
    ) -> Select[Escalation, Patient, Appointment | None, str | None]:
        # Outer joins: an escalation may have no appointment, so the last two columns can be NULL.
        query = (
            select(Escalation, Patient, Appointment, ProcedureType.name)
            .join(Patient, Patient.id == Escalation.patient_id)
            .outerjoin(Appointment, Appointment.id == Escalation.appointment_id)
            .outerjoin(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .where(Escalation.organization_id == organization_id)
        )
        return cast(Select[Escalation, Patient, Appointment | None, str | None], query)

    def acknowledge(
        self, principal: StaffPrincipal, escalation_id: uuid.UUID, *, now: dt.datetime
    ) -> Escalation:
        principal.require(Permission.ESCALATION_HANDLE)
        escalation = self._load(principal, escalation_id)
        if escalation.status is EscalationStatus.RESOLVED:
            raise ConflictError("This escalation is already resolved")
        if escalation.status is EscalationStatus.OPEN:
            escalation.status = EscalationStatus.ACKNOWLEDGED
            escalation.acknowledged_at = now
            escalation.assigned_to_id = principal.user_id
            self._audit(principal, escalation, "ACKNOWLEDGED")
        return escalation

    def resolve(
        self,
        principal: StaffPrincipal,
        escalation_id: uuid.UUID,
        *,
        note: str,
        now: dt.datetime,
    ) -> Escalation:
        principal.require(Permission.ESCALATION_HANDLE)
        escalation = self._load(principal, escalation_id)
        if escalation.status is EscalationStatus.RESOLVED:
            raise ConflictError("This escalation is already resolved")
        escalation.status = EscalationStatus.RESOLVED
        escalation.resolved_at = now
        escalation.resolution_note = note
        escalation.acknowledged_at = escalation.acknowledged_at or now
        escalation.assigned_to_id = escalation.assigned_to_id or principal.user_id
        # The follow-up tasks it opened are done with it.
        self._session.execute(
            update(Task)
            .where(
                Task.escalation_id == escalation.id,
                Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
            )
            .values(status=TaskStatus.DONE, completed_at=now)
        )
        self._audit(principal, escalation, "RESOLVED")
        return escalation

    def _load(self, principal: StaffPrincipal, escalation_id: uuid.UUID) -> Escalation:
        escalation = self._session.scalar(
            select(Escalation)
            .where(
                Escalation.id == escalation_id,
                Escalation.organization_id == principal.organization_id,
            )
            .with_for_update()
        )
        if escalation is None:
            raise NotFoundError("Escalation not found")
        return escalation

    def _audit(self, principal: StaffPrincipal, escalation: Escalation, status: str) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.UPDATE,
            entity_type="escalation",
            entity_id=escalation.id,
            patient_id=escalation.patient_id,
            purpose=PURPOSE,
            details={"status": status},
        )
