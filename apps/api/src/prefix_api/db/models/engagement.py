"""Patient-facing activity: timeline events, check-ins and messages."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import EncryptedString, str_enum
from prefix_api.domain.enums import (
    CheckInResponse,
    CheckInStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    TimelineEventStatus,
)


class PatientTimelineEvent(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    """One protocol step scheduled for one appointment.

    Rescheduling cancels the old events and creates new ones, so history is kept and each
    event is sent at most once. Only one non-cancelled event may exist per step.
    """

    __tablename__ = "patient_timeline_event"
    __table_args__ = (
        Index(
            "uq_patient_timeline_event_active_step",
            "appointment_id",
            "step_id",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
        ),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("prep_step.id", ondelete="RESTRICT")
    )
    due_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    send_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[TimelineEventStatus] = mapped_column(
        str_enum(TimelineEventStatus, "timeline_event_status"),
        default=TimelineEventStatus.PENDING,
        index=True,
    )
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))


class CheckIn(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "check_in"
    __table_args__ = (
        Index(
            "uq_check_in_timeline_event",
            "timeline_event_id",
            unique=True,
            postgresql_where=text("timeline_event_id IS NOT NULL"),
        ),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    timeline_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("patient_timeline_event.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(String(500))
    status: Mapped[CheckInStatus] = mapped_column(
        str_enum(CheckInStatus, "check_in_status"), default=CheckInStatus.PENDING, index=True
    )
    response: Mapped[CheckInResponse | None] = mapped_column(
        str_enum(CheckInResponse, "check_in_response")
    )
    # Free text typed by the patient may contain PHI, so it is encrypted.
    response_text: Mapped[str | None] = mapped_column(EncryptedString("check_in.response_text"))
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "message"
    __table_args__ = (
        # At most one reminder per timeline event: the database backstop for idempotent sends.
        Index(
            "uq_message_outbound_timeline_event",
            "timeline_event_id",
            unique=True,
            postgresql_where=text("direction = 'OUTBOUND' AND timeline_event_id IS NOT NULL"),
        ),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="SET NULL"), index=True
    )
    timeline_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("patient_timeline_event.id", ondelete="SET NULL")
    )
    channel: Mapped[MessageChannel] = mapped_column(str_enum(MessageChannel, "message_channel"))
    direction: Mapped[MessageDirection] = mapped_column(
        str_enum(MessageDirection, "message_direction")
    )
    status: Mapped[MessageStatus] = mapped_column(str_enum(MessageStatus, "message_status"))
    language: Mapped[str] = mapped_column(String(8))
    # What the patient saw or sent.
    body: Mapped[str] = mapped_column(EncryptedString("message.body"))
    # The clinician-approved source text, kept whenever `body` is a translation of it.
    original_body: Mapped[str | None] = mapped_column(EncryptedString("message.original_body"))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(200), index=True)
    error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
