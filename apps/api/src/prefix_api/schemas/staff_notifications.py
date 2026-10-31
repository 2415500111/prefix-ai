import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from prefix_api.domain.enums import StaffNotificationKind
from prefix_api.domain.urgency import UrgentReason
from prefix_api.services.staff_notifications import (
    NotificationSummary,
    StaffFeed,
    StaffNotificationItem,
)


class StaffNotificationOut(BaseModel):
    id: uuid.UUID
    kind: StaffNotificationKind
    # A short line from a fixed template, e.g. "Cannot complete: Clear liquids".
    summary: str
    patient_id: uuid.UUID
    patient_name: str
    appointment_id: uuid.UUID | None
    procedure_name: str | None
    scheduled_at: dt.datetime | None
    # The facility's time zone, for showing when it was raised.
    timezone: str
    # When the patient raised it. The feed is ordered by this, newest first.
    created_at: dt.datetime
    urgent: bool
    urgent_reasons: list[UrgentReason]
    # False once the escalation or task behind it is closed.
    open: bool
    read: bool

    @classmethod
    def from_item(cls, item: StaffNotificationItem) -> StaffNotificationOut:
        notification = item.notification
        return cls(
            id=notification.id,
            kind=notification.kind,
            summary=notification.summary,
            patient_id=notification.patient_id,
            patient_name=item.patient_name,
            appointment_id=notification.appointment_id,
            procedure_name=item.procedure_name,
            scheduled_at=item.scheduled_at,
            timezone=item.timezone,
            created_at=notification.created_at,
            urgent=bool(item.reasons),
            urgent_reasons=list(item.reasons),
            open=item.open,
            read=item.read,
        )


class StaffNotificationSummaryOut(BaseModel):
    """What the bell polls: totals and the newest id. No patient data."""

    latest_id: uuid.UUID | None
    unread_count: int
    urgent_count: int

    @classmethod
    def from_summary(cls, summary: NotificationSummary) -> StaffNotificationSummaryOut:
        return cls(
            latest_id=summary.latest_id,
            unread_count=summary.unread_count,
            urgent_count=summary.urgent_count,
        )


class StaffNotificationFeedOut(StaffNotificationSummaryOut):
    items: list[StaffNotificationOut]

    @classmethod
    def from_feed(cls, feed: StaffFeed) -> StaffNotificationFeedOut:
        return cls(
            items=[StaffNotificationOut.from_item(item) for item in feed.items],
            latest_id=feed.summary.latest_id,
            unread_count=feed.summary.unread_count,
            urgent_count=feed.summary.urgent_count,
        )


class StaffNotificationReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=100)]
