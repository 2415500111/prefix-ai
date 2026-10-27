"""Patient replies arrive by webhook, update check-ins, and escalate problems to people."""

import datetime as dt
from collections.abc import Iterator

import pytest
from api_testkit import Builder, make_test_settings
from fastapi.testclient import TestClient
from messaging_testkit import Booked, FakeTranslator, RecordingProvider, book
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.db.models import CheckIn, Escalation, Message, Task
from prefix_api.domain.enums import (
    AppointmentStatus,
    CheckInResponse,
    CheckInStatus,
    EscalationSeverity,
    MessageDirection,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.replies import parse_reply
from prefix_api.main import create_app
from prefix_api.services.dispatch import dispatch_due_reminders
from prefix_api.services.messaging.providers import twilio_signature

PHONE = "+919811122233"


def sent_check_in(
    build: Builder, session: Session, factory: sessionmaker[Session], title: str
) -> Booked:
    """Book an appointment and send reminders up to and including ``title``."""
    booked = book(build, session, phone=PHONE)
    at = booked.events[title].send_at + dt.timedelta(seconds=1)
    dispatch_due_reminders(factory, RecordingProvider(), FakeTranslator(), now=at, batch_size=50)
    return booked


def reply(client: TestClient, body: str, sender: str = PHONE, **headers: str) -> int:
    response = client.post(
        "/webhooks/twilio",
        data={"From": sender, "Body": body, "MessageSid": "SM-in-1"},
        headers=headers,
    )
    return response.status_code


def check_in_for(session: Session, booked: Booked, title: str) -> CheckIn:
    event = booked.events[title]
    check_in = session.scalar(select(CheckIn).where(CheckIn.timeline_event_id == event.id))
    assert check_in is not None
    session.refresh(check_in)
    return check_in


def test_yes_confirms_the_step(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")

    assert reply(client, "Yes!") == 200

    check_in = check_in_for(db_session, booked, "Arrange escort")
    assert check_in.status is CheckInStatus.ANSWERED
    assert check_in.response is CheckInResponse.YES
    event = booked.events["Arrange escort"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.CONFIRMED
    inbound = db_session.scalar(
        select(Message).where(
            Message.patient_id == booked.patient.id, Message.direction == MessageDirection.INBOUND
        )
    )
    assert inbound is not None
    assert inbound.body == "Yes!"


def test_hindi_yes_is_understood(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")

    reply(client, "हाँ")

    assert check_in_for(db_session, booked, "Arrange escort").response is CheckInResponse.YES


def test_no_on_a_critical_step_escalates_and_flags_the_appointment(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Clear liquids")

    reply(client, "no")

    db_session.refresh(booked.appointment)
    assert booked.appointment.status is AppointmentStatus.AT_RISK
    escalation = db_session.scalar(
        select(Escalation).where(Escalation.patient_id == booked.patient.id)
    )
    assert escalation is not None
    assert escalation.severity is EscalationSeverity.HIGH
    assert "Clear liquids" in escalation.summary
    task = db_session.scalar(select(Task).where(Task.patient_id == booked.patient.id))
    assert task is not None
    assert task.type is TaskType.CALL_PATIENT


def test_no_on_a_non_critical_step_creates_a_call_task_only(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")

    reply(client, "nahi")

    db_session.refresh(booked.appointment)
    assert booked.appointment.status is AppointmentStatus.SCHEDULED
    assert (
        db_session.scalar(select(Escalation).where(Escalation.patient_id == booked.patient.id))
        is None
    )
    assert (
        db_session.scalar(select(Task.type).where(Task.patient_id == booked.patient.id))
        is TaskType.CALL_PATIENT
    )


def test_help_escalates_to_a_nurse(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")

    reply(client, "HELP")

    escalation = db_session.scalar(
        select(Escalation).where(Escalation.patient_id == booked.patient.id)
    )
    assert escalation is not None
    assert escalation.severity is EscalationSeverity.NORMAL
    assert (
        db_session.scalar(select(Task.type).where(Task.patient_id == booked.patient.id))
        is TaskType.NURSE_REVIEW
    )


def test_free_text_goes_to_a_person_and_is_not_interpreted(
    client: TestClient, build: Builder, db_session: Session, session_factory: sessionmaker[Session]
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")

    reply(client, "I have chest pain since this morning")

    assert check_in_for(db_session, booked, "Arrange escort").status is CheckInStatus.PENDING
    task = db_session.scalar(select(Task).where(Task.patient_id == booked.patient.id))
    assert task is not None
    assert task.type is TaskType.NURSE_REVIEW


def test_unknown_numbers_are_ignored(client: TestClient, db_session: Session) -> None:
    before = db_session.scalar(select(Message.id).limit(1))

    assert reply(client, "YES", sender="+15550009999") == 200
    assert db_session.scalar(select(Message.id).limit(1)) == before


@pytest.fixture
def live_client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    settings = make_test_settings(
        messaging_provider="live",
        twilio_account_sid="AC1",
        twilio_auth_token="tok",
        public_api_base_url="https://api.example.com",
    )
    with TestClient(create_app(settings, session_factory=session_factory)) as client:
        yield client


def test_live_webhooks_require_a_valid_twilio_signature(
    live_client: TestClient,
    build: Builder,
    db_session: Session,
    session_factory: sessionmaker[Session],
) -> None:
    booked = sent_check_in(build, db_session, session_factory, "Arrange escort")
    params = {"From": PHONE, "Body": "YES", "MessageSid": "SM-in-1"}
    good = twilio_signature("tok", "https://api.example.com/webhooks/twilio", params)

    assert reply(live_client, "YES", **{"X-Twilio-Signature": "forged"}) == 401
    assert check_in_for(db_session, booked, "Arrange escort").status is CheckInStatus.PENDING
    assert reply(live_client, "YES", **{"X-Twilio-Signature": good}) == 200
    assert check_in_for(db_session, booked, "Arrange escort").status is CheckInStatus.ANSWERED


def test_production_rejects_unsigned_webhooks(session_factory: sessionmaker[Session]) -> None:
    settings = make_test_settings(
        app_env="production", jwt_secret="x" * 40, pii_blind_index_key="y" * 40
    )
    with TestClient(create_app(settings, session_factory=session_factory)) as client:
        assert reply(client, "YES") == 401


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("YES", CheckInResponse.YES),
        (" yes. ", CheckInResponse.YES),
        ("Done", CheckInResponse.YES),
        ("haan", CheckInResponse.YES),
        ("हाँ", CheckInResponse.YES),
        ("हां।", CheckInResponse.YES),
        ("No", CheckInResponse.NO),
        ("not yet", CheckInResponse.NO),
        ("नहीं", CheckInResponse.NO),
        ("help?", CheckInResponse.HELP),
        ("मदद", CheckInResponse.HELP),
        ("yes but I feel dizzy", CheckInResponse.OTHER),
        ("I have chest pain", CheckInResponse.OTHER),
        ("", CheckInResponse.OTHER),
    ],
)
def test_reply_parsing(text: str, expected: CheckInResponse) -> None:
    assert parse_reply(text) is expected
