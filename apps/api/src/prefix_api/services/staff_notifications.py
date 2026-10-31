"""Staff notifications: what patients raised, newest first, with per-person read marks.

An item is written where the patient raises something (``notify_staff``): a problem with a
prep step, a question the assistant hands to a nurse, a HELP reply, a free-text message, or a
reschedule request. Listing is one indexed query ordered by ``created_at DESC, id DESC``;
nothing is re-sorted in Python. Urgency comes from fixed rules (``domain.urgency``), never
from an LLM, and never changes the order.

An item counts as read once this person has opened it, or once anyone has closed the
escalation or task behind it. Reading the feed and marking items read are audited (rule d).
The summary the bell polls holds only totals and an id, never patient data.
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    Escalation,
    Facility,
    Patient,
    ProcedureType,
    StaffNotification,
    StaffNotificationRead,
    Task,
)
from prefix_api.domain.enums import (
    AuditAction,
    EscalationStatus,
    StaffNotificationKind,
    TaskStatus,
)
from prefix_api.domain.errors import NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import Principal, StaffPrincipal
from prefix_api.domain.urgency import UrgentReason, urgent_reasons
from prefix_api.services.audit import record_audit

# How far back the feed reaches, and how many rows it weighs at most for its counts.
WINDOW = dt.timedelta(days=14)
MAX_STATE_ROWS = 1000
MAX_ITEMS = 50
ENTITY = "staff_notification"
PURPOSE_RAISED = "patient_raised"
PURPOSE_FEED = "staff_notifications"
PURPOSE_READ = "staff_notifications_read"
FALLBACK_TIMEZONE = "UTC"
_OPEN_TASK = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)


def notify_staff(
    session: Session,
    *,
    principal: Principal,
    patient: Patient,
    appointment_id: uuid.UUID | None,
    kind: StaffNotificationKind,
    summary: str,
    now: dt.datetime,
    red_flag: bool = False,
    critical_step: bool = False,
    escalation: Escalation | None = None,
    task: Task | None = None,
) -> StaffNotification:
    """Put what the patient raised in front of the care team. ``summary`` comes from a fixed
    template (a step title, a red-flag category), never from an LLM."""
    session.flush()  # the escalation and the task need their ids
    notification = StaffNotification(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        appointment_id=appointment_id,
        escalation_id=escalation.id if escalation else None,
        task_id=task.id if task else None,
        kind=kind,
        summary=summary[:300],
        red_flag=red_flag,
        critical_step=critical_step,
        created_at=now,
    )
    session.add(notification)
    session.flush()
    record_audit(
        session,
        principal=principal,
        action=AuditAction.CREATE,
        entity_type=ENTITY,
        entity_id=notification.id,
        patient_id=patient.id,
        purpose=PURPOSE_RAISED,
        details={"status": kind.value},
    )
    return notification


@dataclass(frozen=True, slots=True)
class _State:
    """What the counts need about one item. No patient data."""

    id: uuid.UUID
    patient_id: uuid.UUID
    reasons: tuple[UrgentReason, ...]
    open: bool
    read: bool

    @property
    def urgent(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True, slots=True)
class NotificationSummary:
    latest_id: uuid.UUID | None
    unread_count: int
    urgent_count: int


@dataclass(frozen=True, slots=True)
class StaffNotificationItem:
    notification: StaffNotification
    patient_name: str
    procedure_name: str | None
    scheduled_at: dt.datetime | None
    timezone: str
    reasons: tuple[UrgentReason, ...]
    open: bool
    read: bool


@dataclass(frozen=True, slots=True)
class StaffFeed:
    items: list[StaffNotificationItem]
    summary: NotificationSummary


def _summary(states: list[_State]) -> NotificationSummary:
    return NotificationSummary(
        latest_id=states[0].id if states else None,
        unread_count=sum(1 for s in states if not s.read),
        urgent_count=sum(1 for s in states if s.urgent and not s.read),
    )


def can_see_notifications(principal: StaffPrincipal) -> bool:
    return principal.can(Permission.ESCALATION_HANDLE) or principal.can(Permission.TASK_MANAGE)


class StaffNotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, principal: StaffPrincipal, *, now: dt.datetime) -> NotificationSummary:
        """Totals for the bell, and the newest id so a client can tell something arrived."""
        self._require(principal)
        return _summary(self._states(principal, now))

    def feed(
        self,
        principal: StaffPrincipal,
        *,
        now: dt.datetime,
        urgent_only: bool = False,
        limit: int = MAX_ITEMS,
    ) -> StaffFeed:
        self._require(principal)
        states = self._states(principal, now)
        shown = [s for s in states if s.urgent or not urgent_only][:limit]
        by_id = {s.id: s for s in shown}
        rows = (
            self._session.execute(
                select(
                    StaffNotification,
                    Patient.first_name,
                    Patient.last_name,
                    ProcedureType.name,
                    Appointment.scheduled_at,
                    Facility.timezone,
                )
                .join(Patient, Patient.id == StaffNotification.patient_id)
                .outerjoin(Appointment, Appointment.id == StaffNotification.appointment_id)
                .outerjoin(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
                .outerjoin(Facility, Facility.id == Appointment.facility_id)
                .where(StaffNotification.id.in_(by_id))
                .order_by(StaffNotification.created_at.desc(), StaffNotification.id.desc())
            ).all()
            if by_id
            else []
        )
        fallback = self._default_timezone(principal.organization_id)
        items = []
        for notification, first, last, procedure, scheduled_at, timezone in rows:
            state = by_id[notification.id]
            items.append(
                StaffNotificationItem(
                    notification=notification,
                    patient_name=f"{first} {last}",
                    procedure_name=procedure,
                    scheduled_at=scheduled_at,
                    timezone=timezone or fallback,
                    reasons=state.reasons,
                    open=state.open,
                    read=state.read,
                )
            )
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.LIST,
                entity_type=ENTITY,
                entity_id=notification.id,
                patient_id=notification.patient_id,
                purpose=PURPOSE_FEED,
            )
        # One entry for the read itself, so an empty feed is audited too.
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.LIST,
            entity_type="staff_notifications",
            purpose=PURPOSE_FEED,
            details={"count": len(items)},
        )
        return StaffFeed(items=items, summary=_summary(states))

    def mark_read(
        self, principal: StaffPrincipal, ids: Iterable[uuid.UUID], *, now: dt.datetime
    ) -> NotificationSummary:
        self._require(principal)
        wanted = set(ids)
        found = self._session.execute(
            select(StaffNotification.id, StaffNotification.patient_id).where(
                StaffNotification.organization_id == principal.organization_id,
                StaffNotification.id.in_(wanted),
            )
        ).all()
        if len(found) != len(wanted):
            raise NotFoundError("Notification not found")
        self._store_reads(principal, [(row[0], row[1]) for row in found], now)
        return self.summary(principal, now=now)

    def mark_all_read(self, principal: StaffPrincipal, *, now: dt.datetime) -> NotificationSummary:
        self._require(principal)
        unread = [(s.id, s.patient_id) for s in self._states(principal, now) if not s.read]
        self._store_reads(principal, unread, now)
        return self.summary(principal, now=now)

    def unread_urgent_patients(
        self, principal: StaffPrincipal, *, now: dt.datetime
    ) -> frozenset[uuid.UUID]:
        """Patients with an urgent item this person has not read (the Overview's red bar)."""
        if not can_see_notifications(principal):
            return frozenset()
        return frozenset(
            s.patient_id for s in self._states(principal, now) if s.urgent and not s.read
        )

    # -- helpers -------------------------------------------------------------------------

    def _require(self, principal: StaffPrincipal) -> None:
        if not can_see_notifications(principal):
            principal.require(Permission.ESCALATION_HANDLE)  # raises with the usual message

    def _states(self, principal: StaffPrincipal, now: dt.datetime) -> list[_State]:
        """Every item in the window, newest first, as the database orders them."""
        rows = self._session.execute(
            select(
                StaffNotification.id,
                StaffNotification.patient_id,
                StaffNotification.red_flag,
                StaffNotification.critical_step,
                StaffNotification.escalation_id,
                StaffNotification.task_id,
                Appointment.scheduled_at,
                Escalation.status,
                Task.status,
                StaffNotificationRead.id,
            )
            .outerjoin(Appointment, Appointment.id == StaffNotification.appointment_id)
            .outerjoin(Escalation, Escalation.id == StaffNotification.escalation_id)
            .outerjoin(Task, Task.id == StaffNotification.task_id)
            .outerjoin(
                StaffNotificationRead,
                and_(
                    StaffNotificationRead.notification_id == StaffNotification.id,
                    StaffNotificationRead.user_id == principal.user_id,
                ),
            )
            .where(
                StaffNotification.organization_id == principal.organization_id,
                StaffNotification.created_at >= now - WINDOW,
            )
            .order_by(StaffNotification.created_at.desc(), StaffNotification.id.desc())
            .limit(MAX_STATE_ROWS)
        ).all()
        states = []
        for row in rows:
            (nid, patient_id, red_flag, critical, esc_id, task_id, scheduled_at) = row[:7]
            escalation_status: EscalationStatus | None = row[7]
            task_status: TaskStatus | None = row[8]
            read_mark: uuid.UUID | None = row[9]  # outer joins: any of these can be NULL
            if esc_id is not None and escalation_status is not None:
                is_open = escalation_status is not EscalationStatus.RESOLVED
            elif task_id is not None and task_status is not None:
                is_open = task_status in _OPEN_TASK
            else:
                is_open = True
            states.append(
                _State(
                    id=nid,
                    patient_id=patient_id,
                    reasons=urgent_reasons(
                        red_flag=red_flag,
                        critical_step=critical,
                        scheduled_at=scheduled_at,
                        now=now,
                    ),
                    open=is_open,
                    read=read_mark is not None or not is_open,
                )
            )
        return states

    def _store_reads(
        self,
        principal: StaffPrincipal,
        items: list[tuple[uuid.UUID, uuid.UUID]],
        now: dt.datetime,
    ) -> None:
        if not items:
            return
        self._session.execute(
            insert(StaffNotificationRead)
            .values(
                [
                    {
                        "id": uuid.uuid7(),
                        "organization_id": principal.organization_id,
                        "notification_id": notification_id,
                        "user_id": principal.user_id,
                        "read_at": now,
                    }
                    for notification_id, _ in items
                ]
            )
            .on_conflict_do_nothing(index_elements=["notification_id", "user_id"])
        )
        for notification_id, patient_id in items:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.UPDATE,
                entity_type=ENTITY,
                entity_id=notification_id,
                patient_id=patient_id,
                purpose=PURPOSE_READ,
                details={"status": "read"},
            )

    def _default_timezone(self, organization_id: uuid.UUID) -> str:
        """For an item without a booking: the hospital's first facility's time zone."""
        timezone = self._session.scalars(
            select(Facility.timezone)
            .where(Facility.organization_id == organization_id)
            .order_by(Facility.created_at, Facility.id)
            .limit(1)
        ).first()
        return timezone or FALLBACK_TIMEZONE
