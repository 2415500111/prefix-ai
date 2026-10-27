"""iCalendar (RFC 5545) export of a procedure, for the patient's own calendar.

Only what the patient needs to turn up on time: procedure name, arrival time, place, and a
link back to the portal. No prep instructions (they can change) and no identifiers.
"""

import datetime as dt
import uuid
from dataclasses import dataclass

PRODID = "-//Prefix AI//Patient Portal//EN"
_LINE_LIMIT = 75  # octets, excluding the CRLF


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    appointment_id: uuid.UUID
    procedure_name: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    location: str
    description: str


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Split a content line into chunks of at most 75 octets without breaking a character."""
    chunks: list[str] = []
    current = ""
    limit = _LINE_LIMIT
    for char in line:
        if len((current + char).encode()) > limit:
            chunks.append(current)
            current = ""
            limit = _LINE_LIMIT - 1  # continuation lines start with a space
        current += char
    chunks.append(current)
    return [chunks[0], *(f" {chunk}" for chunk in chunks[1:])]


def _utc(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def to_ics(event: CalendarEvent, *, now: dt.datetime) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event.appointment_id}@prefix-ai",
        f"DTSTAMP:{_utc(now)}",
        f"DTSTART:{_utc(event.starts_at)}",
        f"DTEND:{_utc(event.ends_at)}",
        f"SUMMARY:{_escape(event.procedure_name)}",
        f"LOCATION:{_escape(event.location)}",
        f"DESCRIPTION:{_escape(event.description)}",
    ]
    for before in ("-P1D", "-PT2H"):
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(event.procedure_name)}",
            f"TRIGGER:{before}",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "".join(f"{chunk}\r\n" for line in lines for chunk in _fold(line))
