"""Coordinator-facing work: risk scores, waitlist, escalations and tasks."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import EncryptedString, str_enum
from prefix_api.domain.enums import (
    EscalationSeverity,
    EscalationSource,
    EscalationStatus,
    RiskLevel,
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
