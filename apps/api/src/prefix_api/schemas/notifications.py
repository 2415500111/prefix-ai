"""The patient's Updates feed.

Items carry a kind and structured fields, never sentences: the portal writes each sentence from
a fixed English or Hindi template, so no AI writes notification text (safety rule a).
"""

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NotificationKind = Literal[
    "step_now",
    "step_soon",
    "care_team_message",
    "reschedule_request",
    "appointment_moved",
    "appointment_cancelled",
]
Urgency = Literal["urgent", "normal"]
NotificationKey = Annotated[
    str, StringConstraints(min_length=1, max_length=120, pattern=r"^[a-z-]+:[0-9a-z:-]+$")
]


class NotificationOut(BaseModel):
    key: str
    kind: NotificationKind
    urgency: Urgency
    created_at: dt.datetime
    read: bool
    appointment_id: uuid.UUID | None
    procedure_name: str | None = None
    # The facility's timezone, for showing times.
    timezone: str | None = None
    # Prep steps: the approved title (translated when a cached translation exists).
    event_id: uuid.UUID | None = None
    step_title: str | None = None
    step_done: bool = False
    due_at: dt.datetime | None = None
    # Appointment changes and approved requests: the procedure's time now.
    scheduled_at: dt.datetime | None = None
    request_status: Literal["pending", "approved", "declined"] | None = None
    # A care-team message, written by a person.
    message: str | None = None


class NotificationFeedOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class NotificationReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[NotificationKey] = Field(min_length=1, max_length=100)


class NotificationReadOut(BaseModel):
    unread_count: int
