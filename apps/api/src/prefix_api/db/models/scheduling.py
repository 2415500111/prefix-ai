import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import str_enum
from prefix_api.domain.enums import AppointmentStatus, CancellationReason


class ProcedureType(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "procedure_type"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    default_duration_minutes: Mapped[int] = mapped_column(Integer)
    or_cost_per_minute: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    requires_sedation: Mapped[bool] = mapped_column(Boolean, default=False)


class Appointment(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "appointment"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="RESTRICT"), index=True
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("facility.id", ondelete="RESTRICT"), index=True
    )
    procedure_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("procedure_type.id", ondelete="RESTRICT"), index=True
    )
    clinician_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    protocol_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("prep_protocol.id", ondelete="RESTRICT")
    )

    scheduled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    arrival_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)

    status: Mapped[AppointmentStatus] = mapped_column(
        str_enum(AppointmentStatus, "appointment_status"),
        default=AppointmentStatus.SCHEDULED,
        index=True,
    )
    cancellation_reason: Mapped[CancellationReason | None] = mapped_column(
        str_enum(CancellationReason, "cancellation_reason")
    )
    cancellation_note: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    external_id: Mapped[str | None] = mapped_column(String(200))
