import datetime as dt
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from prefix_api.domain.conditions import InvalidConditionError, validate_condition
from prefix_api.domain.enums import ProtocolStatus, StepCategory

MAX_OFFSET_MINUTES = 60 * 24 * 60  # 60 days before the procedure

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Instruction = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset_minutes: Annotated[int, Field(ge=0, le=MAX_OFFSET_MINUTES)]
    title: Title
    instruction_text: Instruction
    category: StepCategory
    requires_confirmation: bool = False
    is_critical: bool = False
    conditions: dict[str, Any] | None = None

    @field_validator("conditions")
    @classmethod
    def _valid_conditions(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            try:
                validate_condition(value)
            except InvalidConditionError as exc:
                raise ValueError(str(exc)) from exc
        return value


class ProtocolIn(BaseModel):
    """Full content of a protocol draft. Steps replace the existing ones, in order."""

    model_config = ConfigDict(extra="forbid")

    procedure_type_id: uuid.UUID
    name: Title
    description: Annotated[str, StringConstraints(max_length=4000)] | None = None
    steps: Annotated[list[StepIn], Field(max_length=100)] = []


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Sample protocols ship with the product and must be reviewed before use.
    acknowledge_sample: bool = False


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sort_order: int
    offset_minutes: int
    title: str
    instruction_text: str
    category: StepCategory
    requires_confirmation: bool
    is_critical: bool
    conditions: dict[str, Any] | None


class ProtocolSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    version: int
    procedure_type_id: uuid.UUID
    name: str
    status: ProtocolStatus
    is_sample: bool
    approved_at: dt.datetime | None
    updated_at: dt.datetime


class ProtocolOut(ProtocolSummaryOut):
    description: str | None
    approved_by_id: uuid.UUID | None
    steps: list[StepOut]
