"""Analytics: the numbers, the baseline estimate, the CSV export, and who may see each."""

import datetime as dt
from decimal import Decimal

from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, CheckIn, Organization
from prefix_api.domain.enums import (
    ActorType,
    AppointmentStatus,
    AuditAction,
    CancellationReason,
    CheckInResponse,
    CheckInStatus,
    Role,
)
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.services.appointments import AppointmentService

TODAY = dt.datetime.now(dt.UTC)
START = TODAY.date() - dt.timedelta(days=1)
END = TODAY.date() + dt.timedelta(days=10)


def add_appointment(
    build: Builder,
    db_session: Session,
    first: Booked,
    *,
    days: int,
    status: AppointmentStatus = AppointmentStatus.SCHEDULED,
    reason: CancellationReason | None = None,
) -> Booked:
    """Another procedure in the same hospital, so the analytics see them together."""
    org = db_session.get(Organization, first.patient.organization_id)
    assert org is not None
    patient = build.patient(org)
    coordinator = build.user(org, Role.COORDINATOR)
    principal = StaffPrincipal(
        user_id=coordinator.id, organization_id=org.id, role=Role.COORDINATOR
    )
    now = dt.datetime.now(dt.UTC)
    appointment = AppointmentService(db_session).create(
        principal,
        AppointmentCreate(
            patient_id=patient.id,
            facility_id=first.appointment.facility_id,
            procedure_type_id=first.appointment.procedure_type_id,
            scheduled_at=now + dt.timedelta(days=days),
        ),
        now=now,
    )
    appointment.status = status
    appointment.cancellation_reason = reason
    db_session.flush()
    return Booked(appointment=appointment, patient=patient, events={})


def week_of_procedures(build: Builder, db_session: Session) -> Booked:
    """Four procedures: two cancelled for prep (one of them with a reason from the other group)."""
    first = book(build, db_session, days_ahead=1)
    add_appointment(
        build,
        db_session,
        first,
        days=2,
        status=AppointmentStatus.CANCELLED,
        reason=CancellationReason.NO_ESCORT,
    )
    add_appointment(
        build,
        db_session,
        first,
        days=3,
        status=AppointmentStatus.CANCELLED,
        reason=CancellationReason.PATIENT_REQUESTED,
    )
    add_appointment(build, db_session, first, days=4)
    return first


def coordinator(
    build: Builder, db_session: Session, booked: Booked, settings: Settings
) -> dict[str, str]:
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    return staff_headers(settings, build.user(org, Role.COORDINATOR))


def summary(client: TestClient, headers: dict[str, str], **params: float) -> dict[str, object]:
    query: dict[str, str | float] = {"start": START.isoformat(), "end": END.isoformat(), **params}
    response = client.get("/analytics/summary", headers=headers, params=query)
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


def test_the_rates_count_prep_cancellations_and_the_theatre_time_at_risk(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    headers = coordinator(build, db_session, booked, settings)

    result = summary(client, headers)

    assert result["procedures"] == 4
    assert result["cancelled"] == 2
    assert result["cancellation_rate"] == 50.0
    assert result["prep_cancelled"] == 1
    assert result["prep_share"] == 50.0
    # Colonoscopy: 45 minutes at 50 per minute in the builder, for the one prep cancellation.
    assert result["or_minutes_at_risk"] == 45
    assert Decimal(str(result["or_cost_at_risk"])) == Decimal("2250.00")


def test_check_in_response_rate_counts_only_sent_check_ins(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    sent_at = dt.datetime.now(dt.UTC)
    for status, response in (
        (CheckInStatus.ANSWERED, CheckInResponse.YES),
        (CheckInStatus.PENDING, None),
    ):
        db_session.add(
            CheckIn(
                organization_id=booked.patient.organization_id,
                appointment_id=booked.appointment.id,
                patient_id=booked.patient.id,
                question="Confirm",
                status=status,
                response=response,
                sent_at=sent_at,
            )
        )
    db_session.add(
        CheckIn(
            organization_id=booked.patient.organization_id,
            appointment_id=booked.appointment.id,
            patient_id=booked.patient.id,
            question="Not sent",
            status=CheckInStatus.PENDING,
            sent_at=None,
        )
    )
    db_session.flush()

    result = summary(client, coordinator(build, db_session, booked, settings))

    assert result["checkins_sent"] == 2
    assert result["checkins_answered"] == 1
    assert result["response_rate"] == 50.0


def test_avoided_cancellations_are_only_estimated_against_a_baseline(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    headers = coordinator(build, db_session, booked, settings)

    without = summary(client, headers)
    with_baseline = summary(client, headers, baseline_rate=75)

    assert without["avoided_estimate"] is None
    assert without["or_cost_saved_estimate"] is None
    # 75% of 4 procedures was 3 cancellations; 2 happened, so one was avoided.
    assert with_baseline["avoided_estimate"] == 1
    assert with_baseline["or_minutes_saved_estimate"] == 45


def test_a_range_must_make_sense(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    headers = coordinator(build, db_session, booked, settings)

    backwards = client.get(
        "/analytics/summary", headers=headers, params={"start": "2026-11-10", "end": "2026-11-01"}
    )
    too_long = client.get(
        "/analytics/summary", headers=headers, params={"start": "2025-01-01", "end": "2026-06-01"}
    )

    assert backwards.status_code == 422
    assert too_long.status_code == 422


def test_the_export_has_no_names_and_is_audited(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    headers = coordinator(build, db_session, booked, settings)

    response = client.get(
        "/analytics/export.csv",
        headers=headers,
        params={"start": START.isoformat(), "end": END.isoformat()},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("appointment_id,scheduled_at_utc,procedure_code")
    assert len(lines) == 5  # header plus four procedures
    assert booked.patient.first_name not in response.text
    rows = db_session.scalars(
        select(AuditLog).where(
            AuditLog.actor_type == ActorType.USER, AuditLog.action == AuditAction.EXPORT
        )
    ).all()
    assert any(row.purpose == "analytics_export" for row in rows)


def test_only_coordinators_and_admins_may_export(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = week_of_procedures(build, db_session)
    org = db_session.get(Organization, booked.patient.organization_id)
    assert org is not None
    params = {"start": START.isoformat(), "end": END.isoformat()}

    viewer = staff_headers(settings, build.user(org, Role.VIEWER))
    guest = staff_headers(settings, build.user(org, Role.DEMO_VIEWER))
    guest_export = client.get("/analytics/export.csv", headers=guest, params=params)
    viewer_export = client.get("/analytics/export.csv", headers=viewer, params=params)

    assert guest_export.status_code == 403
    assert viewer_export.status_code == 403
    # Viewers may still read the summary (aggregates only).
    assert client.get("/analytics/summary", headers=viewer, params=params).status_code == 200


def test_the_patient_money_figures_are_exposure_not_savings(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    """Without a baseline there is no saving to claim, only the cost of what was lost."""
    booked = week_of_procedures(build, db_session)

    result = summary(client, coordinator(build, db_session, booked, settings))

    assert result["or_cost_at_risk"] is not None
    assert result["or_cost_saved_estimate"] is None
    assert result["or_minutes_saved_estimate"] is None
