"""Approved steps are translated once, cached, and served to the portal without the LLM."""

import datetime as dt
from dataclasses import dataclass, field

from api_testkit import Builder, patient_headers
from fastapi.testclient import TestClient
from messaging_testkit import FakeTranslator, RecordingProvider, book
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.db.models import Message, PrepStep, PrepStepTranslation
from prefix_api.domain.enums import AppointmentStatus
from prefix_api.services.dispatch import CONFIRM_FOOTERS, dispatch_due_reminders
from prefix_api.services.step_translations import (
    cached_translations,
    translate_step,
    warm_step_translations,
)
from prefix_api.services.translation import Translation

Factory = sessionmaker[Session]


@dataclass
class OneLineTranslator:
    """Returns text that lost the title/instruction structure."""

    name: str = "broken"
    calls: list[str] = field(default_factory=list)

    def translate(self, text: str, language: str) -> Translation:
        self.calls.append(text)
        return Translation(text="सब कुछ एक पंक्ति में", translated=True)


def a_step(build: Builder, db_session: Session) -> PrepStep:
    booked = book(build, db_session)
    step = db_session.get(PrepStep, booked.events["Clear liquids"].step_id)
    assert step is not None
    return step


def cache_size(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(PrepStepTranslation)) or 0


def test_a_step_is_translated_once_and_then_read_from_the_cache(
    build: Builder, db_session: Session
) -> None:
    step = a_step(build, db_session)
    translator = FakeTranslator()

    first = translate_step(db_session, translator, step, "hi-IN")
    second = translate_step(db_session, translator, step, "hi")

    assert first is not None
    assert first.title == "[hi] Clear liquids"
    assert first.instruction == "Instruction for Clear liquids."
    assert second == first
    assert translator.calls == [("Clear liquids\nInstruction for Clear liquids.", "hi")]
    row = db_session.scalar(select(PrepStepTranslation))
    assert row is not None
    assert (row.language, row.translated_by) == ("hi", "fake")


def test_english_and_unsupported_languages_are_never_translated(
    build: Builder, db_session: Session
) -> None:
    step = a_step(build, db_session)
    translator = FakeTranslator()

    assert translate_step(db_session, translator, step, "en") is None
    assert translate_step(db_session, translator, step, "xx") is None
    assert translator.calls == []


def test_failed_or_malformed_translations_are_not_cached(
    build: Builder, db_session: Session
) -> None:
    step = a_step(build, db_session)

    assert translate_step(db_session, FakeTranslator(fail=True), step, "hi") is None
    assert translate_step(db_session, OneLineTranslator(), step, "hi") is None
    assert cache_size(db_session) == 0


def test_warm_up_translates_steps_for_upcoming_non_english_patients(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    hindi = book(build, db_session, language="hi")
    book(build, db_session, language="en")
    now = dt.datetime.now(dt.UTC)

    first = warm_step_translations(session_factory, FakeTranslator(), now=now)
    second = warm_step_translations(session_factory, FakeTranslator(), now=now)

    assert first == {"missing": 3, "translated": 3}
    assert second == {"missing": 0, "translated": 0}
    step_ids = [event.step_id for event in hindi.events.values()]
    assert len(cached_translations(db_session, step_ids, "hi")) == 3


def test_warm_up_skips_cancelled_and_distant_appointments(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    cancelled = book(build, db_session, language="hi")
    cancelled.appointment.status = AppointmentStatus.CANCELLED
    book(build, db_session, language="hi", days_ahead=30)
    db_session.flush()

    outcome = warm_step_translations(session_factory, FakeTranslator(), now=dt.datetime.now(dt.UTC))

    assert outcome["missing"] == 0


def test_portal_shows_cached_translations_and_falls_back_to_english(
    client: TestClient,
    settings: Settings,
    build: Builder,
    db_session: Session,
    session_factory: Factory,
) -> None:
    booked = book(build, db_session, language="hi")
    headers = patient_headers(settings, booked.patient)

    def steps() -> list[dict[str, str]]:
        response = client.get("/patient/appointments?lang=hi", headers=headers)
        assert response.status_code == 200
        result: list[dict[str, str]] = response.json()[0]["steps"]
        return result

    before = steps()
    warm_step_translations(session_factory, FakeTranslator(), now=dt.datetime.now(dt.UTC))
    after = steps()

    assert {s["language"] for s in before} == {"en"}
    assert before[0]["title"] == "Low-fibre diet"
    assert {s["language"] for s in after} == {"hi"}
    assert after[0]["title"] == "[hi] Low-fibre diet"
    english = client.get("/patient/appointments", headers=headers).json()[0]["steps"]
    assert english[0]["title"] == "Low-fibre diet"


def test_hindi_reminders_use_the_cache_and_the_fixed_hindi_reply_footer(
    build: Builder, db_session: Session, session_factory: Factory
) -> None:
    booked = book(build, db_session, language="hi")
    translator = FakeTranslator()
    at = booked.events["Clear liquids"].send_at + dt.timedelta(seconds=1)

    dispatch_due_reminders(session_factory, RecordingProvider(), translator, now=at, batch_size=50)

    message = db_session.scalar(
        select(Message).where(Message.timeline_event_id == booked.events["Clear liquids"].id)
    )
    assert message is not None
    assert message.body.startswith("Prefix AI: [hi] Clear liquids\n")
    assert message.body.endswith(CONFIRM_FOOTERS["hi"])
    assert message.original_body is not None
    assert message.original_body.startswith("Clear liquids\nInstruction for Clear liquids.")
    assert cache_size(db_session) == 3
    # The footer itself was never sent to the translator.
    assert all("Reply YES" not in text for text, _ in translator.calls)
