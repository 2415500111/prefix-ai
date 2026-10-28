"""Waitlist backfill: who is offered a released slot, and how a slot is booked exactly once."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

import pytest
from api_testkit import Builder, StepSpec, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.db.models import (
    Appointment,
    AuditLog,
    BackfillOffer,
    Organization,
    Patient,
    PatientTimelineEvent,
    ProcedureType,
    User,
    WaitlistEntry,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CancellationReason,
    OfferStatus,
    Role,
    WaitlistStatus,
)
from prefix_api.domain.errors import ConflictError, NotFoundError, PermissionDeniedError
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentCancel, AppointmentCreate
from prefix_api.schemas.waitlist import WaitlistEntryCreate
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.demo import DEMO_SLUG, populate_demo
from prefix_api.services.waitlist import PURPOSE, WaitlistService

KOLKATA = ZoneInfo("Asia/Kolkata")
DAY = 24 * 60
# The prep starts up to three days before the procedure.
STEPS = [StepSpec(3 * DAY, "Clear liquids"), StepSpec(1 * DAY, "Low-fibre diet")]


class Hospital:
    """One hospital with an approved prep protocol, a coordinator and a demo viewer."""

    def __init__(self, build: Builder, session: Session) -> None:
        self.build = build
        self.session = session
        self.org: Organization = build.organization()
        self.facility = build.facility(self.org, timezone="Asia/Kolkata")
        self.procedure: ProcedureType = build.procedure_type(self.org)
        build.approved_protocol(self.org, self.procedure, STEPS)
        self.coordinator_user = build.user(self.org, Role.COORDINATOR)
        self.viewer_user = build.user(self.org, Role.DEMO_VIEWER)
        self.coordinator = StaffPrincipal(
            user_id=self.coordinator_user.id,
            organization_id=self.org.id,
            role=self.coordinator_user.role,
        )
        self.viewer = StaffPrincipal(
            user_id=self.viewer_user.id,
            organization_id=self.org.id,
            role=self.viewer_user.role,
        )
        self.now = dt.datetime.now(dt.UTC)
        self.service = WaitlistService(session)

    def patient(self, name: str) -> Patient:
        return self.build.patient(self.org, first_name=name)

    def book(self, patient: Patient, scheduled: dt.datetime) -> Appointment:
        return AppointmentService(self.session).create(
            self.coordinator,
            AppointmentCreate(
                patient_id=patient.id,
                facility_id=self.facility.id,
                procedure_type_id=self.procedure.id,
                scheduled_at=scheduled,
            ),
            now=self.now,
        )

    def released_slot(self, scheduled: dt.datetime | None = None) -> Appointment:
        """A slot that was booked and then released by a cancellation."""
        when = scheduled or self.now + dt.timedelta(days=5)
        appointment = self.book(self.patient("Released"), when)
        AppointmentService(self.session).cancel(
            self.coordinator,
            appointment.id,
            AppointmentCancel(reason=CancellationReason.PATIENT_REQUESTED),
            now=self.now,
        )
        self.session.flush()
        return appointment

    def local_day(self) -> dt.date:
        """The date of the default released slot, in the hospital's timezone."""
        return (self.now + dt.timedelta(days=5)).astimezone(KOLKATA).date()

    def enrol(
        self,
        patient: Patient,
        *,
        earliest: dt.date,
        latest: dt.date,
        priority: int = 0,
    ) -> WaitlistEntry:
        row = self.service.add(
            self.coordinator,
            WaitlistEntryCreate(
                patient_id=patient.id,
                procedure_type_id=self.procedure.id,
                earliest_date=earliest,
                latest_date=latest,
                priority=priority,
            ),
        )
        return row.entry


@pytest.fixture
def hospital(build: Builder, db_session: Session) -> Hospital:
    return Hospital(build, db_session)


def _entry_status(session: Session, entry_id: uuid.UUID) -> WaitlistStatus:
    entry = session.get(WaitlistEntry, entry_id)
    assert entry is not None
    return entry.status


def _in_window(hospital: Hospital, patient: Patient, priority: int = 0) -> WaitlistEntry:
    day = hospital.local_day()
    return hospital.enrol(
        patient,
        earliest=day - dt.timedelta(days=1),
        latest=day + dt.timedelta(days=1),
        priority=priority,
    )


def test_the_slot_date_must_fall_inside_the_window(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    day = hospital.local_day()
    inside = _in_window(hospital, hospital.patient("Inside"))
    hospital.enrol(
        hospital.patient("Later"),
        earliest=day + dt.timedelta(days=2),
        latest=day + dt.timedelta(days=4),
    )

    view = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    assert view.offer.waitlist_entry_id == inside.id


def test_the_highest_priority_patient_is_offered_first(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    _in_window(hospital, hospital.patient("Routine"), priority=0)
    urgent = _in_window(hospital, hospital.patient("Urgent"), priority=5)

    view = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    assert view.offer.waitlist_entry_id == urgent.id
    assert view.offer.reasons[0] == "Priority 5"


def test_a_slot_has_at_most_one_open_offer(hospital: Hospital, db_session: Session) -> None:
    slot = hospital.released_slot()
    first_entry = _in_window(hospital, hospital.patient("First"), priority=5)
    second_entry = _in_window(hospital, hospital.patient("Second"))

    first = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)
    again = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    assert again.offer.id == first.offer.id
    open_offers = db_session.scalar(
        select(func.count())
        .select_from(BackfillOffer)
        .where(
            BackfillOffer.slot_appointment_id == slot.id, BackfillOffer.status == OfferStatus.OPEN
        )
    )
    assert open_offers == 1
    assert _entry_status(db_session, first_entry.id) is WaitlistStatus.OFFERED
    assert _entry_status(db_session, second_entry.id) is WaitlistStatus.ACTIVE


def test_nobody_is_offered_a_slot_too_soon_for_the_prep(hospital: Hospital) -> None:
    slot = hospital.released_slot(scheduled=hospital.now + dt.timedelta(days=2))
    _in_window(hospital, hospital.patient("Too late"))

    with pytest.raises(NotFoundError):
        hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)


def test_accepting_books_the_patient_into_the_slot(hospital: Hospital, db_session: Session) -> None:
    slot = hospital.released_slot()
    entry = _in_window(hospital, hospital.patient("Asha"))
    offer = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    booked = hospital.service.accept(hospital.coordinator, offer.offer.id, now=hospital.now)

    assert booked.patient_id == entry.patient_id
    assert booked.scheduled_at == slot.scheduled_at
    assert booked.status is AppointmentStatus.SCHEDULED
    timeline = db_session.scalars(
        select(PatientTimelineEvent).where(PatientTimelineEvent.appointment_id == booked.id)
    ).all()
    assert timeline
    assert _entry_status(db_session, entry.id) is WaitlistStatus.BOOKED
    released = hospital.service.released_slots(hospital.coordinator, now=hospital.now)
    assert slot.id not in {row.appointment.id for row in released}


def test_a_filled_slot_cannot_be_booked_again(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    _in_window(hospital, hospital.patient("First"))
    _in_window(hospital, hospital.patient("Second"))
    offer = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)
    hospital.service.accept(hospital.coordinator, offer.offer.id, now=hospital.now)

    with pytest.raises(ConflictError):
        hospital.service.accept(hospital.coordinator, offer.offer.id, now=hospital.now)
    with pytest.raises(ConflictError):
        hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)


def test_the_database_allows_only_one_accepted_offer_per_slot(
    hospital: Hospital, db_session: Session
) -> None:
    slot = hospital.released_slot()
    first = _in_window(hospital, hospital.patient("First"))
    second = _in_window(hospital, hospital.patient("Second"))

    # Two accepted offers for one slot would be a double booking, so the database refuses it.
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add_all(
            [
                BackfillOffer(
                    organization_id=hospital.org.id,
                    slot_appointment_id=slot.id,
                    waitlist_entry_id=entry.id,
                    status=OfferStatus.ACCEPTED,
                    reasons=[],
                )
                for entry in (first, second)
            ]
        )


def test_a_declined_patient_is_not_offered_the_slot_again(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    first = _in_window(hospital, hospital.patient("Urgent"), priority=5)
    second = _in_window(hospital, hospital.patient("Routine"))

    offered = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)
    assert offered.offer.waitlist_entry_id == first.id
    declined = hospital.service.decline(hospital.coordinator, offered.offer.id)
    assert declined.offer.status is OfferStatus.DECLINED
    assert declined.offer.waitlist_entry_id == first.id
    assert first.status is WaitlistStatus.ACTIVE

    next_offer = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)
    assert next_offer.offer.waitlist_entry_id == second.id

    hospital.service.decline(hospital.coordinator, next_offer.offer.id)
    with pytest.raises(NotFoundError):
        hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)


def test_a_patient_who_already_has_this_procedure_is_skipped(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    booked_already = hospital.patient("Booked")
    hospital.book(booked_already, hospital.now + dt.timedelta(days=9))
    _in_window(hospital, booked_already)
    free = _in_window(hospital, hospital.patient("Free"))

    view = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    assert view.offer.waitlist_entry_id == free.id


def test_the_slot_date_is_read_in_the_facility_timezone(hospital: Hospital) -> None:
    # 00:30 in Kolkata is still the previous day in UTC, so the window must use local dates.
    day = hospital.local_day()
    slot = hospital.released_slot(
        scheduled=dt.datetime.combine(day, dt.time(0, 30), tzinfo=KOLKATA)
    )
    previous_day_only = hospital.enrol(
        hospital.patient("UTC day"),
        earliest=day - dt.timedelta(days=1),
        latest=day - dt.timedelta(days=1),
    )
    local = hospital.enrol(hospital.patient("Local day"), earliest=day, latest=day)

    view = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    assert view.offer.waitlist_entry_id == local.id
    assert view.offer.waitlist_entry_id != previous_day_only.id


def test_an_offered_entry_cannot_be_removed_but_an_active_one_can(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    entry = _in_window(hospital, hospital.patient("Offered"))
    hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    with pytest.raises(ConflictError):
        hospital.service.remove(hospital.coordinator, entry.id)

    waiting = _in_window(hospital, hospital.patient("Waiting"))
    removed = hospital.service.remove(hospital.coordinator, waiting.id)
    assert removed.entry.status is WaitlistStatus.REMOVED


def test_viewers_can_look_but_cannot_offer_or_book(hospital: Hospital) -> None:
    slot = hospital.released_slot()
    _in_window(hospital, hospital.patient("Asha"))
    offer = hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    with pytest.raises(PermissionDeniedError):
        hospital.service.find_backfill(hospital.viewer, slot.id, now=hospital.now)
    with pytest.raises(PermissionDeniedError):
        hospital.service.accept(hospital.viewer, offer.offer.id, now=hospital.now)
    with pytest.raises(PermissionDeniedError):
        hospital.service.decline(hospital.viewer, offer.offer.id)


def test_offers_and_candidate_reads_are_audited(hospital: Hospital, db_session: Session) -> None:
    slot = hospital.released_slot()
    _in_window(hospital, hospital.patient("Asha"))
    hospital.service.find_backfill(hospital.coordinator, slot.id, now=hospital.now)

    rows = db_session.scalars(select(AuditLog).where(AuditLog.purpose == PURPOSE)).all()

    actions = {(row.entity_type, row.action) for row in rows}
    assert ("backfill_offer", AuditAction.CREATE) in actions
    assert ("waitlist_entry", AuditAction.LIST) in actions
    assert all(row.patient_id is not None for row in rows)


def test_the_waitlist_api_runs_the_whole_backfill(
    hospital: Hospital, client: TestClient, settings: Settings
) -> None:
    slot = hospital.released_slot()
    patient = hospital.patient("Asha")
    coordinator = staff_headers(settings, hospital.coordinator_user)
    viewer = staff_headers(settings, hospital.viewer_user)
    day = hospital.local_day()
    body = {
        "patient_id": str(patient.id),
        "procedure_type_id": str(hospital.procedure.id),
        "earliest_date": (day - dt.timedelta(days=1)).isoformat(),
        "latest_date": (day + dt.timedelta(days=1)).isoformat(),
    }

    invalid = {**body, "latest_date": (day - dt.timedelta(days=2)).isoformat()}
    assert client.post("/waitlist", json=invalid, headers=coordinator).status_code == 422
    created = client.post("/waitlist", json=body, headers=coordinator)
    assert created.status_code == 201
    assert created.json()["patient_name"].startswith("Asha ")

    slots = client.get("/waitlist/slots", headers=coordinator).json()
    assert [row["appointment_id"] for row in slots] == [str(slot.id)]
    assert slots[0]["open_offer"] is None

    found = client.post(f"/waitlist/slots/{slot.id}/find-backfill", headers=coordinator)
    assert found.status_code == 200
    offer = found.json()
    assert offer["status"] == "OPEN"
    assert offer["patient_id"] == str(patient.id)
    assert offer["reasons"]

    accepted = client.post(f"/waitlist/offers/{offer['id']}/accept", headers=coordinator)
    assert accepted.status_code == 200
    assert accepted.json()["patient_id"] == str(patient.id)
    assert (
        client.post(f"/waitlist/offers/{offer['id']}/accept", headers=coordinator).status_code
        == 409
    )

    assert client.get("/waitlist/slots", headers=viewer).status_code == 200
    assert (
        client.post(f"/waitlist/slots/{slot.id}/find-backfill", headers=viewer).status_code == 403
    )


def test_the_demo_hospital_has_a_slot_that_can_be_backfilled(
    session_factory: sessionmaker[Session], db_session: Session
) -> None:
    now = dt.datetime.now(dt.UTC)
    admin_password = "demo-admin-password"  # pragma: allowlist secret
    populate_demo(session_factory, now=now, admin_password=admin_password)
    org = db_session.scalar(select(Organization).where(Organization.slug == DEMO_SLUG))
    assert org is not None
    coordinator_user = db_session.scalar(
        select(User).where(User.organization_id == org.id, User.role == Role.COORDINATOR)
    )
    assert coordinator_user is not None
    coordinator = StaffPrincipal(
        user_id=coordinator_user.id, organization_id=org.id, role=Role.COORDINATOR
    )
    service = WaitlistService(db_session)

    slots = service.released_slots(coordinator, now=now)
    assert len(slots) == 1
    offer = service.find_backfill(coordinator, slots[0].appointment.id, now=now)

    assert offer.patient.first_name != "Released"
    assert len(service.entries(coordinator, status=WaitlistStatus.OFFERED)) == 1
