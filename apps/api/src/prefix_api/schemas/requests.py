import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints


class RequestOut(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    procedure_name: str
    scheduled_at: dt.datetime
    status: Literal["pending", "approved", "declined"]
    created_at: dt.datetime
    decided_at: dt.datetime | None


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: AwareDatetime


class StaffMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class StaffMessageOut(BaseModel):
    id: uuid.UUID
    created_at: dt.datetime


class BadgesOut(BaseModel):
    open_tasks: int
    open_escalations: int
    pending_requests: int
