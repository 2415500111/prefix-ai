"""The patient's Updates feed, derived when it is read.

Nothing new runs when a reminder is sent or a booking changes: every item comes from records
that already exist (the prep timeline, care-team messages, reschedule requests and the
appointment's audited changes). Only the patient's read marks are stored. Every query is scoped
to the signed-in patient, and reading the feed or marking items read is audited (rule d).
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    AuditLog,
    CheckIn,
    Facility,
    Message,
    PatientNotificationRead,
    PatientTimelineEvent,
    PrepStep,
    ProcedureType,
    Task,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    MessageChannel,
    MessageDirection,
    TaskStatus,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.errors import NotFoundError
from prefix_api.domain.portal import StepState, step_view
from prefix_api.domain.principal import PatientPrincipal
from prefix_api.schemas.notifications import NotificationFeedOut, NotificationOut
from prefix_api.services.audit import record_audit
from prefix_api.services.patient_contact import CARE_TEAM_PROVIDER
from prefix_api.services.portal import SHOW_PAST_FOR
from prefix_api.services.requests import request_status
from prefix_api.services.step_translations import cached_translations
from prefix_api.services.translation import SOURCE_LANGUAGE

# How far back changes, answers and messages are shown.
WINDOW = dt.timedelta(days=14)
# Steps starting within this time show as "coming up".
SOON = dt.timedelta(hours=24)
# Approving a request moves the procedure in the same transaction, so its audited move is the
# same change and is not shown twice. The two timestamps come from different clocks (the
# database's transaction time and the request's time), hence a tolerance.
SAME_CHANGE = dt.timedelta(minutes=2)
MAX_MESSAGES = 20
ENTITY = "patient_notifications"
_DOING = frozenset({StepState.DUE, StepState.OVERDUE, StepState.ACTIVE})
_OPEN_TASK = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)
_CLOSED = (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED)


@dataclass(frozen=True, slots=True)
class _Booking:
    appointment: Appointment
    procedure_name: str
    timezone: str


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def feed(
        self, principal: PatientPrincipal, *, now: dt.datetime, language: str = SOURCE_LANGUAGE
    ) -> NotificationFeedOut:
        """Newest first. Step titles come back in ``language`` when a cached translation of the
        approved text exists."""
        items = self._items(principal, now, language)
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type=ENTITY,
            entity_id=principal.patient_id,
            patient_id=principal.patient_id,
            purpose="patient_self_access",
            details={"count": len(items)},
        )
        return NotificationFeedOut(items=items, unread_count=_unread(items))

    def mark_read(
        self, principal: PatientPrincipal, keys: Iterable[str], *, now: dt.datetime
    ) -> int:
        """Marks the given items read and returns the unread count. Keys that are not in the
        patient's current feed are refused, so a patient can only mark their own items."""
        wanted = set(keys)
        items = self._items(principal, now, SOURCE_LANGUAGE)
        if not wanted <= {item.key for item in items}:
            raise NotFoundError("Update not found")
        self._store(principal, wanted, now)
        return sum(1 for item in items if not item.read and item.key not in wanted)

    def mark_all_read(self, principal: PatientPrincipal, *, now: dt.datetime) -> int:
        items = self._items(principal, now, SOURCE_LANGUAGE)
        self._store(principal, {item.key for item in items if not item.read}, now)
        return 0

    # -- building the feed ---------------------------------------------------------------

    def _items(
        self, principal: PatientPrincipal, now: dt.datetime, language: str
    ) -> list[NotificationOut]:
        bookings = self._bookings(principal, now)
        items: list[NotificationOut] = []
        for booking in bookings.values():
            cancelled_at = booking.appointment.cancelled_at
            if booking.appointment.status is AppointmentStatus.CANCELLED:
                if cancelled_at is not None:
                    items.append(_cancelled(booking, cancelled_at))
            else:
                items.extend(self._steps(booking, now, language))
        approvals = self._requests(principal, bookings, now, items)
        items.extend(self._moves(principal, bookings, now, approvals))
        items.extend(self._messages(principal, bookings, now))

        read = set(
            self._session.scalars(
                select(PatientNotificationRead.key).where(
                    PatientNotificationRead.organization_id == principal.organization_id,
                    PatientNotificationRead.patient_id == principal.patient_id,
                )
            )
        )
        items = [
            item.model_copy(update={"read": True}) if item.key in read else item for item in items
        ]
        items.sort(key=lambda item: (item.created_at, item.key), reverse=True)
        return items

    def _bookings(self, principal: PatientPrincipal, now: dt.datetime) -> dict[uuid.UUID, _Booking]:
        """Upcoming procedures (as in the portal) and those cancelled recently."""
        rows = self._session.execute(
            select(Appointment, ProcedureType.name, Facility.timezone)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .join(Facility, Facility.id == Appointment.facility_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.patient_id == principal.patient_id,
                or_(
                    Appointment.status.not_in(_CLOSED)
                    & (Appointment.scheduled_at >= now - SHOW_PAST_FOR),
                    (Appointment.status == AppointmentStatus.CANCELLED)
                    & (Appointment.cancelled_at >= now - WINDOW),
                ),
            )
        ).all()
        return {
            appointment.id: _Booking(appointment, procedure_name, timezone)
            for appointment, procedure_name, timezone in rows
        }

    def _steps(self, booking: _Booking, now: dt.datetime, language: str) -> list[NotificationOut]:
        rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep, CheckIn.response)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .outerjoin(CheckIn, CheckIn.timeline_event_id == PatientTimelineEvent.id)
            .where(
                PatientTimelineEvent.appointment_id == booking.appointment.id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
        ).all()
        translations = cached_translations(self._session, (row[1].id for row in rows), language)
        items = []
        for event, step, response in rows:
            state = step_view(
                status=event.status,
                requires_confirmation=step.requires_confirmation,
                send_at=event.send_at,
                due_at=event.due_at,
                last_response=response,
                now=now,
            ).state
            starts_at = min(event.send_at, event.due_at)
            translated = translations.get(step.id)
            title = translated.title if translated else step.title
            if now >= starts_at:
                done = state is StepState.DONE
                items.append(
                    NotificationOut(
                        key=f"step-due:{event.id}",
                        kind="step_now",
                        urgency="urgent" if step.is_critical and state in _DOING else "normal",
                        created_at=starts_at,
                        # A step the patient has already done needs no attention.
                        read=done,
                        appointment_id=booking.appointment.id,
                        procedure_name=booking.procedure_name,
                        timezone=booking.timezone,
                        event_id=event.id,
                        step_title=title,
                        step_done=done,
                        due_at=event.due_at,
                    )
                )
            elif state is StepState.UPCOMING and starts_at - now <= SOON:
                items.append(
                    NotificationOut(
                        key=f"step-soon:{event.id}",
                        kind="step_soon",
                        urgency="normal",
                        created_at=starts_at - SOON,
                        read=False,
                        appointment_id=booking.appointment.id,
                        procedure_name=booking.procedure_name,
                        timezone=booking.timezone,
                        event_id=event.id,
                        step_title=title,
                        due_at=event.due_at,
                    )
                )
        return items

    def _requests(
        self,
        principal: PatientPrincipal,
        bookings: dict[uuid.UUID, _Booking],
        now: dt.datetime,
        items: list[NotificationOut],
    ) -> dict[uuid.UUID, list[dt.datetime]]:
        """Adds one item per reschedule request (its current status) and returns when each
        appointment's requests were approved."""
        tasks = self._session.scalars(
            select(Task).where(
                Task.organization_id == principal.organization_id,
                Task.patient_id == principal.patient_id,
                Task.type == TaskType.RESCHEDULE,
                Task.appointment_id.in_(list(bookings)),
                or_(Task.status.in_(_OPEN_TASK), Task.completed_at >= now - WINDOW),
            )
        ).all()
        approvals: dict[uuid.UUID, list[dt.datetime]] = {}
        for task in tasks:
            booking = bookings[task.appointment_id] if task.appointment_id else None
            if booking is None:  # pragma: no cover - the query only returns these appointments
                continue
            status = request_status(task)
            answered_at = task.completed_at if status != "pending" else None
            if status == "approved" and answered_at is not None:
                approvals.setdefault(booking.appointment.id, []).append(answered_at)
            items.append(
                NotificationOut(
                    key=f"reschedule:{task.id}:{status}",
                    kind="reschedule_request",
                    urgency="normal" if status == "pending" else "urgent",
                    created_at=answered_at or task.created_at,
                    read=False,
                    appointment_id=booking.appointment.id,
                    procedure_name=booking.procedure_name,
                    timezone=booking.timezone,
                    request_status=status,
                    scheduled_at=(
                        booking.appointment.scheduled_at if status == "approved" else None
                    ),
                )
            )
        return approvals

    def _moves(
        self,
        principal: PatientPrincipal,
        bookings: dict[uuid.UUID, _Booking],
        now: dt.datetime,
        approvals: dict[uuid.UUID, list[dt.datetime]],
    ) -> list[NotificationOut]:
        """The latest time each open procedure was moved by staff, from the audit log."""
        open_ids = [
            booking.appointment.id
            for booking in bookings.values()
            if booking.appointment.status not in _CLOSED
        ]
        rows = self._session.execute(
            select(AuditLog.id, AuditLog.entity_id, AuditLog.occurred_at)
            .where(
                AuditLog.organization_id == principal.organization_id,
                AuditLog.patient_id == principal.patient_id,
                AuditLog.entity_type == "appointment",
                AuditLog.action == AuditAction.UPDATE,
                AuditLog.purpose == "appointment_reschedule",
                AuditLog.entity_id.in_(open_ids),
                AuditLog.occurred_at >= now - WINDOW,
            )
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        ).all()
        items = []
        seen: set[uuid.UUID] = set()
        for audit_id, appointment_id, occurred_at in rows:
            if appointment_id is None or appointment_id in seen:
                continue
            seen.add(appointment_id)
            if any(
                abs(approved_at - occurred_at) <= SAME_CHANGE
                for approved_at in approvals.get(appointment_id, [])
            ):
                continue  # The approved request already tells the patient the new time.
            booking = bookings[appointment_id]
            items.append(
                NotificationOut(
                    key=f"moved:{audit_id}",
                    kind="appointment_moved",
                    urgency="urgent",
                    created_at=occurred_at,
                    read=False,
                    appointment_id=appointment_id,
                    procedure_name=booking.procedure_name,
                    timezone=booking.timezone,
                    scheduled_at=booking.appointment.scheduled_at,
                )
            )
        return items

    def _messages(
        self,
        principal: PatientPrincipal,
        bookings: dict[uuid.UUID, _Booking],
        now: dt.datetime,
    ) -> list[NotificationOut]:
        """Messages a person on the care team wrote to the patient (never automated reminders)."""
        messages = self._session.scalars(
            select(Message)
            .where(
                Message.organization_id == principal.organization_id,
                Message.patient_id == principal.patient_id,
                Message.channel == MessageChannel.PORTAL,
                Message.direction == MessageDirection.OUTBOUND,
                Message.provider == CARE_TEAM_PROVIDER,
                Message.sent_at >= now - WINDOW,
            )
            .order_by(Message.sent_at.desc())
            .limit(MAX_MESSAGES)
        ).all()
        items = []
        for message in messages:
            if message.sent_at is None:  # pragma: no cover - the query filters on sent_at
                continue
            booking = bookings.get(message.appointment_id) if message.appointment_id else None
            items.append(
                NotificationOut(
                    key=f"message:{message.id}",
                    kind="care_team_message",
                    urgency="normal",
                    created_at=message.sent_at,
                    read=False,
                    appointment_id=message.appointment_id,
                    procedure_name=booking.procedure_name if booking else None,
                    timezone=booking.timezone if booking else None,
                    message=message.body,
                )
            )
        return items

    def _store(self, principal: PatientPrincipal, keys: set[str], now: dt.datetime) -> None:
        if not keys:
            return
        self._session.execute(
            insert(PatientNotificationRead)
            .values(
                [
                    {
                        "id": uuid.uuid7(),
                        "organization_id": principal.organization_id,
                        "patient_id": principal.patient_id,
                        "key": key,
                        "read_at": now,
                    }
                    for key in sorted(keys)
                ]
            )
            .on_conflict_do_nothing(index_elements=["patient_id", "key"])
        )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.UPDATE,
            entity_type=ENTITY,
            entity_id=principal.patient_id,
            patient_id=principal.patient_id,
            purpose="patient_notifications_read",
            details={"count": len(keys)},
        )


def _cancelled(booking: _Booking, cancelled_at: dt.datetime) -> NotificationOut:
    appointment = booking.appointment
    return NotificationOut(
        key=f"cancelled:{appointment.id}",
        kind="appointment_cancelled",
        urgency="urgent",
        created_at=cancelled_at,
        read=False,
        appointment_id=appointment.id,
        procedure_name=booking.procedure_name,
        timezone=booking.timezone,
        scheduled_at=appointment.scheduled_at,
    )


def _unread(items: list[NotificationOut]) -> int:
    return sum(1 for item in items if not item.read)
