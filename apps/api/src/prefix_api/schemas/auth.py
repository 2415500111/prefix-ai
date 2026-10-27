import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from prefix_api.domain.enums import Role

OpaqueToken = Annotated[str, StringConstraints(min_length=20, max_length=200)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Not validated as an email: every bad login must get the same generic 401.
    email: Annotated[str, StringConstraints(min_length=1, max_length=320)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: OpaqueToken


class TokenPairOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    access_expires_at: dt.datetime
    refresh_token: str
    refresh_expires_at: dt.datetime


class MeOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    role: Role
