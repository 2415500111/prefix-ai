"""Shared fixtures for dispatch and inbound-message tests."""

import datetime as dt
from dataclasses import dataclass, field

from api_testkit import Builder, StepSpec
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, Patient, PatientTimelineEvent, PrepStep
from prefix_api.domain.enums import MessageChannel, Role
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.messaging.base import MessagingError, OutboundMessage, SendResult
from prefix_api.services.translation import Translation

DAY = 24 * 60
STEPS = [
    StepSpec(3 * DAY, "Low-fibre diet"),
    StepSpec(1 * DAY, "Clear liquids", is_critical=True, requires_confirmation=True),
    StepSpec(2 * DAY, "Arrange escort", requires_confirmation=True),
]


@dataclass
class RecordingProvider:
    sent: list[OutboundMessage] = field(default_factory=list)
    fail_with: str | None = None

    def send(self, message: OutboundMessage) -> SendResult:
        if self.fail_with:
            raise MessagingError(self.fail_with)
        self.sent.append(message)
        return SendResult(provider="fake", provider_message_id=f"fake-{len(self.sent)}")


@dataclass
class FakeTranslator:
    fail: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def translate(self, text: str, language: str) -> Translation:
        self.calls.append((text, language))
        if self.fail or language == "en":
            return Translation(text=text, translated=False)
        return Translation(text=f"[{language}] {text}", translated=True)


@dataclass
class Booked:
    appointment: Appointment
    patient: Patient
    events: dict[str, PatientTimelineEvent]


def book(
    build: Builder,
    session: Session,
    *,
    days_ahead: int = 10,
    consent: bool = True,
    channel: MessageChannel = MessageChannel.SMS,
    language: str = "en",
    phone: str | None = None,
) -> Booked:
    org = build.organization()
    facility = build.facility(org)
    procedure = build.procedure_type(org)
    build.approved_protocol(org, procedure, STEPS)
    patient_fields: dict[str, object] = {
        "consent_to_message": consent,
        "preferred_channel": channel,
        "preferred_language": language,
    }
    if phone is not None:
        patient_fields["phone"] = phone
    patient = build.patient(org, **patient_fields)
    coordinator = build.user(org, Role.COORDINATOR)
    principal = StaffPrincipal(
        user_id=coordinator.id, organization_id=org.id, role=coordinator.role
    )
    now = dt.datetime.now(dt.UTC)
    appointment = AppointmentService(session).create(
        principal,
        AppointmentCreate(
            patient_id=patient.id,
            facility_id=facility.id,
            procedure_type_id=procedure.id,
            scheduled_at=now + dt.timedelta(days=days_ahead),
        ),
        now=now,
    )
    session.flush()
    rows = session.execute(
        select(PrepStep.title, PatientTimelineEvent)
        .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
        .where(PatientTimelineEvent.appointment_id == appointment.id)
    ).all()
    events = {row[0]: row[1] for row in rows}
    return Booked(appointment=appointment, patient=patient, events=events)
