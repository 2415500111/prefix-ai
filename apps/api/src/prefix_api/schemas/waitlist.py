import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prefix_api.domain.enums import OfferStatus, WaitlistStatus


class WaitlistEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: uuid.UUID
    procedure_type_id: uuid.UUID
    earliest_date: dt.date
    latest_date: dt.date
    priority: Annotated[int, Field(ge=0, le=10)] = 0

    @model_validator(mode="after")
    def _window_in_order(self) -> WaitlistEntryCreate:
        if self.latest_date < self.earliest_date:
            raise ValueError("latest_date must not be before earliest_date")
        return self


class WaitlistEntryOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    procedure_name: str
    earliest_date: dt.date
    latest_date: dt.date
    priority: int
    status: WaitlistStatus


class OfferOut(BaseModel):
    id: uuid.UUID
    status: OfferStatus
    waitlist_entry_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    reasons: list[str]


class ReleasedSlotOut(BaseModel):
    appointment_id: uuid.UUID
    procedure_name: str
    facility_name: str
    scheduled_at: dt.datetime
    open_offer: OfferOut | None
