import datetime as dt
import uuid
import zoneinfo
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
)

from prefix_api.domain.enums import Role

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _valid_timezone(value: str) -> str:
    if value not in zoneinfo.available_timezones():
        raise ValueError(f"Unknown IANA timezone '{value}'")
    return value


Timezone = Annotated[str, AfterValidator(_valid_timezone)]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: ShortText
    role: Role
    password: Annotated[str, StringConstraints(min_length=12, max_length=200)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    last_login_at: dt.datetime | None


class FacilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    timezone: Timezone
    address: Annotated[str, StringConstraints(max_length=500)] | None = None
    maps_url: HttpUrl | None = None
    phone: Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{6,14}$")] | None = None


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    timezone: str
    address: str | None
    maps_url: str | None
    phone: str | None


class ProcedureTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{2,64}$")]
    name: ShortText
    default_duration_minutes: Annotated[int, Field(ge=5, le=1440)]
    or_cost_per_minute: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
    requires_sedation: bool = False


class ProcedureTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    default_duration_minutes: int
    or_cost_per_minute: Decimal
    requires_sedation: bool
