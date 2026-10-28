import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from prefix_api.domain.enums import TaskStatus, TaskType


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TaskType
    title: str
    status: TaskStatus
    patient_id: uuid.UUID | None
    appointment_id: uuid.UUID | None
    due_at: dt.datetime | None
    completed_at: dt.datetime | None
