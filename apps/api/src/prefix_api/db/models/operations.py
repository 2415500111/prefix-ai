"""Coordinator-facing work: risk scores, waitlist, escalations and tasks."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import EncryptedString, str_enum
from prefix_api.domain.enums import (
    EscalationSeverity,
    EscalationSource,
    EscalationStatus,
    OfferStatus,
    RiskLevel,
    StaffNotificationKind,
    TaskStatus,
    TaskType,
    WaitlistStatus,
)


class RiskScore(UUIDPrimaryKey, TenantScoped, Base):
    __tablename__ = "risk_score"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),)

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[RiskLevel] = mapped_column(str_enum(RiskLevel, "risk_level"))
    # Readable reasons, e.g. [{"feature": "escort_unconfirmed", "weight": 20, "label": "..."}]
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    model_version: Mapped[str] = mapped_column(String(40))
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)


class WaitlistEntry(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "waitlist_entry"
    __table_args__ = (CheckConstraint("latest_date >= earliest_date", name="date_window_valid"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    procedure_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("procedure_type.id", ondelete="RESTRICT"), index=True
    )
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("facility.id", ondelete="SET NULL")
    )
    earliest_date: Mapped[dt.date] = mapped_column(Date)
    latest_date: Mapped[dt.date] = mapped_column(Date)
    # Prep the patient has already completed, e.g. {"labs_done": true, "escort_arranged": true}
    prep_flags: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[WaitlistStatus] = mapped_column(
        str_enum(WaitlistStatus, "waitlist_status"), default=WaitlistStatus.ACTIVE, index=True
    )


class Escalation(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "escalation"
    # The nurse inbox lists a hospital's escalations newest first.
    __table_args__ = (Index("ix_escalation_newest", "organization_id", "created_at", "id"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[EscalationSource] = mapped_column(
        str_enum(EscalationSource, "escalation_source")
    )
    severity: Mapped[EscalationSeverity] = mapped_column(
        str_enum(EscalationSeverity, "escalation_severity")
    )
    status: Mapped[EscalationStatus] = mapped_column(
        str_enum(EscalationStatus, "escalation_status"),
        default=EscalationStatus.OPEN,
        index=True,
    )
    # May describe symptoms in the patient's words, so it is encrypted.
    summary: Mapped[str] = mapped_column(EncryptedString("escalation.summary"))
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(
        EncryptedString("escalation.resolution_note")
    )


class Task(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "task"
    # The Requests page lists a hospital's reschedule requests newest first.
    __table_args__ = (Index("ix_task_newest", "organization_id", "type", "created_at", "id"),)

    type: Mapped[TaskType] = mapped_column(str_enum(TaskType, "task_type"))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), default=TaskStatus.OPEN, index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("escalation.id", ondelete="SET NULL")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class StaffNotification(UUIDPrimaryKey, TenantScoped, Base):
    """Something a patient raised that the care team should see: a problem with a step, a
    question for a nurse, a free-text reply or a reschedule request.

    Written when it happens, so the feed is one indexed query, newest first. The flags record
    the facts the urgency rules need (``domain.urgency``); whether the item is still open is
    read from the escalation or task it points to.
    """

    __tablename__ = "staff_notification"
    __table_args__ = (Index("ix_staff_notification_newest", "organization_id", "created_at", "id"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("escalation.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("task.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[StaffNotificationKind] = mapped_column(
        str_enum(StaffNotificationKind, "staff_notification_kind")
    )
    # A short line from a fixed template, e.g. "Cannot complete: Clear liquids". It can name
    # a symptom, so it is encrypted like the escalation summary.
    summary: Mapped[str] = mapped_column(EncryptedString("staff_notification.summary"))
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    critical_step: Mapped[bool] = mapped_column(Boolean, default=False)
    # When the patient raised it (the service's clock, not the database's).
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StaffNotificationRead(UUIDPrimaryKey, TenantScoped, Base):
    """One staff member has read one notification. Read marks are per person."""

    __tablename__ = "staff_notification_read"
    __table_args__ = (UniqueConstraint("notification_id", "user_id"),)

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff_notification.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    read_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class BackfillOffer(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    """One offer of a released slot to a waitlisted patient.

    At most one OPEN offer and at most one ACCEPTED offer may exist per slot. The database
    enforces both, so two staff members cannot book the same slot.
    """

    __tablename__ = "backfill_offer"
    __table_args__ = (
        Index(
            "uq_backfill_offer_open_per_slot",
            "slot_appointment_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
        Index(
            "uq_backfill_offer_accepted_per_slot",
            "slot_appointment_id",
            unique=True,
            postgresql_where=text("status = 'ACCEPTED'"),
        ),
    )

    slot_appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    waitlist_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("waitlist_entry.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[OfferStatus] = mapped_column(
        str_enum(OfferStatus, "offer_status"), default=OfferStatus.OPEN, index=True
    )
    booked_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="SET NULL")
    )
    # Why this patient fits the slot, kept so the coordinator still sees them after a reload.
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
