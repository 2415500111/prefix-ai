"""Database triggers from migration 0003 that back safety rule (a), tested with raw SQL so
they hold even if application code is bypassed."""

import datetime as dt
import uuid

import pytest
from api_testkit import Builder
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    Organization,
    PatientTimelineEvent,
    PrepProtocol,
    PrepStep,
)
from prefix_api.domain.enums import ProtocolStatus, StepCategory


def _protocol(build: Builder, status: ProtocolStatus) -> PrepProtocol:
    org = build.organization()
    approver = build.user(org)
    protocol = PrepProtocol(
        organization_id=org.id,
        family_id=uuid.uuid7(),
        version=1,
        procedure_type_id=build.procedure_type(org).id,
        name="Guarded",
        steps=[
            PrepStep(
                organization_id=org.id,
                offset_minutes=60,
                title="Fast",
                instruction_text="Nothing to eat.",
                category=StepCategory.FASTING,
            )
        ],
    )
    build.session.add(protocol)
    build.session.flush()
    if status is not ProtocolStatus.DRAFT:
        protocol.status = ProtocolStatus.APPROVED
        protocol.approved_by_id = approver.id
        protocol.approved_at = dt.datetime.now(dt.UTC)
        build.session.flush()
    if status is ProtocolStatus.RETIRED:
        protocol.status = ProtocolStatus.RETIRED
        build.session.flush()
    return protocol


@pytest.fixture
def approved(build: Builder) -> PrepProtocol:
    return _protocol(build, ProtocolStatus.APPROVED)


def _assert_rejected(session: Session, sql: str, **params: object) -> None:
    with pytest.raises(DBAPIError, match=r"cannot|only"), session.begin_nested():
        session.execute(text(sql), params)


def test_approved_protocol_content_is_immutable(
    db_session: Session, approved: PrepProtocol
) -> None:
    _assert_rejected(
        db_session, "UPDATE prep_protocol SET name = 'tampered' WHERE id = :id", id=approved.id
    )
    _assert_rejected(
        db_session, "UPDATE prep_protocol SET status = 'DRAFT' WHERE id = :id", id=approved.id
    )
    _assert_rejected(db_session, "DELETE FROM prep_protocol WHERE id = :id", id=approved.id)


def test_approved_steps_are_immutable(db_session: Session, approved: PrepProtocol) -> None:
    step_id = approved.steps[0].id

    _assert_rejected(
        db_session, "UPDATE prep_step SET instruction_text = 'x' WHERE id = :id", id=step_id
    )
    _assert_rejected(db_session, "DELETE FROM prep_step WHERE id = :id", id=step_id)
    _assert_rejected(
        db_session,
        "INSERT INTO prep_step (id, organization_id, protocol_id, sort_order, offset_minutes,"
        " title, instruction_text, category, requires_confirmation, is_critical)"
        " VALUES (gen_random_uuid(), :org, :pid, 1, 10, 't', 'x', 'DIET', false, false)",
        org=approved.organization_id,
        pid=approved.id,
    )


def test_retiring_an_approved_version_is_allowed(
    db_session: Session, approved: PrepProtocol
) -> None:
    db_session.execute(
        text("UPDATE prep_protocol SET status = 'RETIRED' WHERE id = :id"), {"id": approved.id}
    )


def test_retired_protocol_is_immutable(build: Builder, db_session: Session) -> None:
    retired = _protocol(build, ProtocolStatus.RETIRED)

    _assert_rejected(
        db_session, "UPDATE prep_protocol SET status = 'APPROVED' WHERE id = :id", id=retired.id
    )


def test_drafts_remain_editable(build: Builder, db_session: Session) -> None:
    draft = _protocol(build, ProtocolStatus.DRAFT)

    db_session.execute(
        text("UPDATE prep_step SET instruction_text = 'edited' WHERE protocol_id = :id"),
        {"id": draft.id},
    )
    db_session.execute(text("DELETE FROM prep_protocol WHERE id = :id"), {"id": draft.id})


def _timeline_event(build: Builder, protocol: PrepProtocol) -> PatientTimelineEvent:
    org_id = protocol.organization_id
    org = build.session.get(Organization, org_id)
    assert org is not None
    patient = build.patient(org)
    now = dt.datetime.now(dt.UTC)
    appointment = Appointment(
        organization_id=org_id,
        patient_id=patient.id,
        facility_id=build.facility(org).id,
        procedure_type_id=protocol.procedure_type_id,
        scheduled_at=now + dt.timedelta(days=3),
        duration_minutes=30,
    )
    build.session.add(appointment)
    build.session.flush()
    return PatientTimelineEvent(
        organization_id=org_id,
        appointment_id=appointment.id,
        patient_id=patient.id,
        step_id=protocol.steps[0].id,
        due_at=now,
        send_at=now,
    )


def test_timeline_events_accept_approved_steps(
    build: Builder, db_session: Session, approved: PrepProtocol
) -> None:
    db_session.add(_timeline_event(build, approved))
    db_session.flush()


def test_timeline_events_reject_unapproved_steps(build: Builder, db_session: Session) -> None:
    draft = _protocol(build, ProtocolStatus.DRAFT)
    event = _timeline_event(build, draft)

    with db_session.begin_nested():
        db_session.add(event)
        with pytest.raises(DBAPIError, match="APPROVED"):
            db_session.flush()
