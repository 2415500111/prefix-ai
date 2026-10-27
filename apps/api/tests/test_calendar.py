"""Calendar (.ics) export of a procedure for the patient."""

import datetime as dt
import uuid
from dataclasses import replace

from api_testkit import Builder, patient_headers
from fastapi.testclient import TestClient
from messaging_testkit import book
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog
from prefix_api.domain.calendar import CalendarEvent, to_ics
from prefix_api.domain.enums import AuditAction

START = dt.datetime(2026, 11, 20, 3, 30, tzinfo=dt.UTC)


EVENT = CalendarEvent(
    appointment_id=uuid.UUID(int=1),
    procedure_name="Colonoscopy",
    starts_at=START,
    ends_at=START + dt.timedelta(minutes=90),
    location="City Hospital, Ring Road; Gate 2",
    description="Your prep plan and checklist: https://example.com/p/home",
)


def unfold(ics: str) -> list[str]:
    return ics.replace("\r\n ", "").split("\r\n")


def test_ics_has_the_procedure_time_place_and_alarms() -> None:
    ics = to_ics(EVENT, now=START - dt.timedelta(days=5))
    lines = unfold(ics)

    assert lines[0] == "BEGIN:VCALENDAR"
    assert "DTSTART:20261120T033000Z" in lines
    assert "DTEND:20261120T050000Z" in lines
    assert "SUMMARY:Colonoscopy" in lines
    assert "LOCATION:City Hospital\\, Ring Road\\; Gate 2" in lines
    assert f"UID:{uuid.UUID(int=1)}@prefix-ai" in lines
    assert lines.count("BEGIN:VALARM") == 2
    assert ics.endswith("END:VCALENDAR\r\n")


def test_long_and_non_latin_lines_are_folded_safely() -> None:
    location = "अस्पताल, " * 30
    ics = to_ics(replace(EVENT, location=location), now=START)

    for line in ics.split("\r\n"):
        assert len(line.encode()) <= 75
    assert f"LOCATION:{location.replace(',', '\\,')}" in unfold(ics)


def test_portal_calendar_download(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    booked = book(build, db_session)
    url = f"/patient/appointments/{booked.appointment.id}/calendar.ics"

    response = client.get(url, headers=patient_headers(settings, booked.patient))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "SUMMARY:Colonoscopy" in body
    assert booked.patient.first_name not in body
    assert db_session.scalar(
        select(AuditLog.id).where(
            AuditLog.patient_id == booked.patient.id, AuditLog.action == AuditAction.EXPORT
        )
    )


def test_calendar_of_another_patient_is_not_found(
    client: TestClient, settings: Settings, build: Builder, db_session: Session
) -> None:
    mine = book(build, db_session)
    theirs = book(build, db_session)

    response = client.get(
        f"/patient/appointments/{theirs.appointment.id}/calendar.ics",
        headers=patient_headers(settings, mine.patient),
    )

    assert response.status_code == 404
