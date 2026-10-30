"""The nurse inbox: escalations that need a person, newest first.

Urgency is shown, not sorted on: the same fixed rules as the staff notifications
(``domain.urgency``) mark an item urgent, and the order is always the time it was raised.
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy import Row, Select, select, update
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    Escalation,
    Facility,
    Patient,
    ProcedureType,
    StaffNotification,
    Task,
)
from prefix_api.domain.enums import (
    AuditAction,
    EscalationSource,
    EscalationStatus,
    TaskStatus,
)
from prefix_api.domain.errors import ConflictError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.domain.urgency import UrgentReason, urgent_reasons
from prefix_api.services.audit import record_audit

InboxFilter = Literal["open", "resolved", "all"]
PURPOSE = "escalation_handling"
_STATUSES: dict[InboxFilter, tuple[EscalationStatus, ...]] = {
    "open": (EscalationStatus.OPEN, EscalationStatus.ACKNOWLEDGED),
    "resolved": (EscalationStatus.RESOLVED,),
    "all": tuple(EscalationStatus),
}
_InboxRow = Row[
    Escalation, Patient, Appointment | None, str | None, str | None, StaffNotification | None
]
_InboxSelect = Select[
    Escalation, Patient, Appointment | None, str | None, str | None, StaffNotification | None
]


def _to_item(row: _InboxRow, now: dt.datetime) -> InboxItem:
    """Read the joined columns by position; mypy cannot unpack a Row of this query."""
    escalation: Escalation = row[0]
    patient: Patient = row[1]
    appointment: Appointment | None = row[2]
    procedure_name: str | None = row[3]
    timezone: str | None = row[4]
    notification: StaffNotification | None = row[5]
    reasons = urgent_reasons(
        red_flag=escalation.source is EscalationSource.RED_FLAG
        or (notification is not None and notification.red_flag),
        critical_step=notification is not None and notification.critical_step,
        scheduled_at=appointment.scheduled_at if appointment else None,
        now=now,
    )
    return InboxItem(escalation, patient, appointment, procedure_name, timezone, reasons)


@dataclass(frozen=True, slots=True)
class InboxItem:
    escalation: Escalation
    patient: Patient
    appointment: Appointment | None
    procedure_name: str | None
    # The facility's time zone; None when the escalation has no booking.
    timezone: str | None
    urgent_reasons: tuple[UrgentReason, ...]


class EscalationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def inbox(
        self,
        principal: StaffPrincipal,
        *,
        now: dt.datetime,
        status: InboxFilter = "open",
        limit: int = 100,
    ) -> list[InboxItem]:
        """Newest first by when it was raised (``created_at DESC, id DESC``, indexed)."""
        principal.require(Permission.ESCALATION_HANDLE)
        rows = self._session.execute(
            self._query(principal.organization_id)
            .where(Escalation.status.in_(_STATUSES[status]))
            .order_by(Escalation.created_at.desc(), Escalation.id.desc())
            .limit(limit)
        ).all()
        items = []
        for row in rows:
            item = _to_item(row, now)
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

    def item(
        self, principal: StaffPrincipal, escalation_id: uuid.UUID, *, now: dt.datetime
    ) -> InboxItem:
        """One escalation in the same shape as the inbox (used after changing it)."""
        principal.require(Permission.ESCALATION_HANDLE)
        row = self._session.execute(
            self._query(principal.organization_id).where(Escalation.id == escalation_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("Escalation not found")
        item = _to_item(row, now)
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

    def _query(self, organization_id: uuid.UUID) -> _InboxSelect:
        # Outer joins: an escalation may have no appointment, and only those a patient raised
        # have a notification (which records the urgency facts), so those columns can be NULL.
        query = (
            select(
                Escalation,
                Patient,
                Appointment,
                ProcedureType.name,
                Facility.timezone,
                StaffNotification,
            )
            .join(Patient, Patient.id == Escalation.patient_id)
            .outerjoin(Appointment, Appointment.id == Escalation.appointment_id)
            .outerjoin(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .outerjoin(Facility, Facility.id == Appointment.facility_id)
            .outerjoin(StaffNotification, StaffNotification.escalation_id == Escalation.id)
            .where(Escalation.organization_id == organization_id)
        )
        return cast(_InboxSelect, query)

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
