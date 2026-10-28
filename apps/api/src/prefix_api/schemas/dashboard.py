import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from prefix_api.domain.enums import (
    AppointmentStatus,
    CheckInResponse,
    EscalationSeverity,
    EscalationStatus,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    RiskLevel,
    TaskStatus,
    TaskType,
    TimelineEventStatus,
)


class UpcomingOut(BaseModel):
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    procedure_name: str
    facility_name: str
    scheduled_at: dt.datetime
    status: AppointmentStatus
    readiness: int
    required_steps: int
    confirmed_steps: int
    problem_steps: int
    open_escalations: int
    open_tasks: int
    risk_score: int
    risk_level: RiskLevel
    # The reasons behind the score, strongest first, in plain words.
    risk_reasons: list[str]


class DrawerStepOut(BaseModel):
    event_id: uuid.UUID
    title: str
    status: TimelineEventStatus
    due_at: dt.datetime
    requires_confirmation: bool
    is_critical: bool
    response: CheckInResponse | None


class DrawerMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: MessageChannel
    direction: MessageDirection
    status: MessageStatus
    body: str
    error: str | None
    created_at: dt.datetime


class DrawerEscalationOut(BaseModel):
    id: uuid.UUID
    severity: EscalationSeverity
    status: EscalationStatus
    summary: str
    created_at: dt.datetime


class DrawerTaskOut(BaseModel):
    id: uuid.UUID
    type: TaskType
    title: str
    status: TaskStatus
    due_at: dt.datetime | None


class DrawerOut(BaseModel):
    appointment: UpcomingOut
    steps: list[DrawerStepOut]
    messages: list[DrawerMessageOut]
    escalations: list[DrawerEscalationOut]
    tasks: list[DrawerTaskOut]


class QueueItemOut(BaseModel):
    id: uuid.UUID
    type: TaskType
    title: str
    status: TaskStatus
    patient_id: uuid.UUID | None
    patient_name: str
    appointment_id: uuid.UUID | None
    due_at: dt.datetime | None
    sla: str


class ResendOut(BaseModel):
    queued: int
