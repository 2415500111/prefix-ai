"""What the patient portal shows. Deliberately small: no internal ids beyond what actions need."""

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from prefix_api.domain.enums import AppointmentStatus, StepCategory
from prefix_api.domain.portal import StepState

PatientNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class PortalFacility(BaseModel):
    name: str
    address: str | None
    maps_url: str | None
    phone: str | None
    timezone: str


class PortalStep(BaseModel):
    event_id: uuid.UUID
    title: str
    instruction: str
    category: StepCategory
    is_critical: bool
    requires_confirmation: bool
    due_at: dt.datetime
    state: StepState
    can_confirm: bool
    can_report_problem: bool


class PortalAppointment(BaseModel):
    id: uuid.UUID
    procedure_name: str
    scheduled_at: dt.datetime
    arrival_at: dt.datetime | None
    duration_minutes: int
    status: AppointmentStatus
    facility: PortalFacility
    steps: list[PortalStep]
    reschedule_requested: bool


class ProblemReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: PatientNote | None = None


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: PatientNote | None = None
