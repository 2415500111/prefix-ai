import datetime as dt
import uuid
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from prefix_api.domain.enums import (
    AppointmentStatus,
    CancellationReason,
    StepCategory,
    TimelineEventStatus,
)


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: uuid.UUID
    facility_id: uuid.UUID
    procedure_type_id: uuid.UUID
    scheduled_at: AwareDatetime
    arrival_at: AwareDatetime | None = None
    duration_minutes: Annotated[int, Field(ge=5, le=1440)] | None = None
    clinician_id: uuid.UUID | None = None
    # Required only when several approved protocols exist for the procedure type.
    protocol_id: uuid.UUID | None = None


class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: AwareDatetime
    arrival_at: AwareDatetime | None = None


class AppointmentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: CancellationReason
    note: Annotated[str, StringConstraints(max_length=1000)] | None = None


class TimelineEventOut(BaseModel):
    id: uuid.UUID
    step_id: uuid.UUID
    title: str
    category: StepCategory
    is_critical: bool
    requires_confirmation: bool
    due_at: dt.datetime
    send_at: dt.datetime
    status: TimelineEventStatus
    sent_at: dt.datetime | None
    confirmed_at: dt.datetime | None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    facility_id: uuid.UUID
    procedure_type_id: uuid.UUID
    clinician_id: uuid.UUID | None
    protocol_id: uuid.UUID | None
    scheduled_at: dt.datetime
    arrival_at: dt.datetime | None
    duration_minutes: int
    status: AppointmentStatus
    cancellation_reason: CancellationReason | None
    cancelled_at: dt.datetime | None


class AppointmentDetailOut(AppointmentOut):
    timeline: list[TimelineEventOut]
