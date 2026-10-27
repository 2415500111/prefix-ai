"""Reminder dispatch: due events are sent exactly once, with consent, from approved text."""

import datetime as dt

import pytest
from api_testkit import Builder
from messaging_testkit import Booked, FakeTranslator, RecordingProvider, book
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.db.models import AuditLog, CheckIn, Message
from prefix_api.domain.enums import (
    ActorType,
    AppointmentStatus,
    CheckInStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TimelineEventStatus,
)
from prefix_api.services.dispatch import (
    CONFIRM_FOOTER,
    STALE_SENDING_AFTER,
    ReminderSender,
    claim_due_events,
    dispatch_due_reminders,
)

Factory = sessionmaker[Session]


def run(
    factory: Factory,
    provider: RecordingProvider,
    *,
    at: dt.datetime,
    translator: FakeTranslator | None = None,
) -> dict[str, int]:
    return dispatch_due_reminders(
        factory, provider, translator or FakeTranslator(), now=at, batch_size=50
    )


def due_time(booked: Booked, title: str) -> dt.datetime:
    return booked.events[title].send_at + dt.timedelta(seconds=1)


def test_due_reminder_is_sent_once_with_a_check_in(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    provider = RecordingProvider()
    at = due_time(booked, "Clear liquids")

    first = run(session_factory, provider, at=at)
    second = run(session_factory, provider, at=at)

    titles = [m.body.split("\n")[0] for m in provider.sent]
    assert titles == [
        "Prefix AI: Low-fibre diet",
        "Prefix AI: Arrange escort",
        "Prefix AI: Clear liquids",
    ]
    assert first["claimed"] == 3
    assert second["claimed"] == 0
    event = booked.events["Clear liquids"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.SENT
    check_in = db_session.scalar(select(CheckIn).where(CheckIn.timeline_event_id == event.id))
    assert check_in is not None
    assert check_in.status is CheckInStatus.PENDING
    assert CONFIRM_FOOTER in provider.sent[2].body


def test_reminders_are_not_sent_before_they_are_due(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    provider = RecordingProvider()

    run(
        session_factory,
        provider,
        at=booked.events["Low-fibre diet"].send_at - dt.timedelta(minutes=1),
    )

    assert provider.sent == []


def test_message_contains_only_approved_text_and_no_patient_name(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    provider = RecordingProvider()

    run(session_factory, provider, at=due_time(booked, "Low-fibre diet"))

    [sent] = provider.sent
    assert sent.to == booked.patient.phone
    assert sent.body == "Prefix AI: Low-fibre diet\nInstruction for Low-fibre diet."
    assert booked.patient.first_name not in sent.body
    assert booked.patient.last_name not in sent.body


def test_no_consent_means_no_message(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, consent=False)
    provider = RecordingProvider()

    run(session_factory, provider, at=due_time(booked, "Low-fibre diet"))

    assert provider.sent == []
    event = booked.events["Low-fibre diet"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.SKIPPED
    assert event.last_error == "Patient has not consented to messages"


def test_portal_only_patients_get_no_message(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, channel=MessageChannel.PORTAL)
    provider = RecordingProvider()

    run(session_factory, provider, at=due_time(booked, "Low-fibre diet"))

    assert provider.sent == []


def test_email_patients_get_email(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, channel=MessageChannel.EMAIL)
    provider = RecordingProvider()

    run(session_factory, provider, at=due_time(booked, "Low-fibre diet"))

    [sent] = provider.sent
    assert sent.channel is MessageChannel.EMAIL
    assert sent.to == booked.patient.email


def test_provider_failure_is_recorded_and_not_retried(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    at = due_time(booked, "Low-fibre diet")

    run(
        session_factory,
        RecordingProvider(fail_with="Twilio rejected the message (HTTP 400)"),
        at=at,
    )
    retry = RecordingProvider()
    run(session_factory, retry, at=at)

    event = booked.events["Low-fibre diet"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.FAILED
    assert event.last_error == "Twilio rejected the message (HTTP 400)"
    message = db_session.scalar(select(Message).where(Message.timeline_event_id == event.id))
    assert message is not None
    assert message.status is MessageStatus.FAILED
    assert retry.sent == []


def test_translated_reminder_keeps_the_approved_original(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, language="hi")
    provider = RecordingProvider()

    run(session_factory, provider, at=due_time(booked, "Low-fibre diet"))

    message = db_session.scalar(select(Message).where(Message.patient_id == booked.patient.id))
    assert message is not None
    assert message.body.startswith("Prefix AI: [hi] Low-fibre diet")
    assert message.original_body == "Low-fibre diet\nInstruction for Low-fibre diet."
    assert message.language == "hi"


def test_translation_failure_sends_the_approved_text(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, language="hi")
    provider = RecordingProvider()

    run(
        session_factory,
        provider,
        at=due_time(booked, "Low-fibre diet"),
        translator=FakeTranslator(fail=True),
    )

    message = db_session.scalar(select(Message).where(Message.patient_id == booked.patient.id))
    assert message is not None
    assert message.body == "Prefix AI: Low-fibre diet\nInstruction for Low-fibre diet."
    assert message.original_body is None
    assert message.language == "en"


def test_cancelled_while_sending_is_not_sent(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    at = due_time(booked, "Low-fibre diet")
    claimed = claim_due_events(db_session, now=at, limit=10)
    booked.appointment.status = AppointmentStatus.CANCELLED
    db_session.commit()
    provider = RecordingProvider()

    for event_id in claimed:
        ReminderSender(db_session, provider, FakeTranslator()).send(event_id, now=at)

    assert provider.sent == []
    event = booked.events["Low-fibre diet"]
    db_session.refresh(event)
    assert event.status is TimelineEventStatus.CANCELLED


def test_stuck_sends_are_failed_not_resent(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    at = due_time(booked, "Low-fibre diet")
    claim_due_events(db_session, now=at, limit=10)
    provider = RecordingProvider()

    # Staleness is judged against the database clock that stamped the claim.
    later = dt.datetime.now(dt.UTC) + STALE_SENDING_AFTER + dt.timedelta(minutes=1)
    outcome = run(session_factory, provider, at=later)

    event = booked.events["Low-fibre diet"]
    db_session.refresh(event)
    assert outcome["stale_failed"] == 1
    assert event.status is TimelineEventStatus.FAILED
    assert "not retried" in (event.last_error or "")


def test_database_allows_one_reminder_per_event(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)
    run(session_factory, RecordingProvider(), at=due_time(booked, "Low-fibre diet"))
    event = booked.events["Low-fibre diet"]

    duplicate = Message(
        organization_id=event.organization_id,
        patient_id=event.patient_id,
        timeline_event_id=event.id,
        channel=MessageChannel.SMS,
        direction=MessageDirection.OUTBOUND,
        status=MessageStatus.QUEUED,
        language="en",
        body="again",
    )
    with db_session.begin_nested():
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()


def test_dispatch_is_audited_as_the_system(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session)

    run(session_factory, RecordingProvider(), at=due_time(booked, "Low-fibre diet"))

    rows = db_session.scalars(
        select(AuditLog).where(
            AuditLog.patient_id == booked.patient.id, AuditLog.actor_type == ActorType.SYSTEM
        )
    ).all()
    assert {(r.entity_type, r.purpose) for r in rows} == {
        ("patient", "prep_reminder"),
        ("message", "prep_reminder"),
    }
