import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from prefix_api.domain.enums import MessageChannel

E164Phone = Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{6,14}$")]
LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
EGFR = Annotated[Decimal, Field(ge=0, le=200, max_digits=5, decimal_places=1)]


class ConditionFlags(BaseModel):
    on_anticoagulant: bool = False
    diabetic_on_insulin: bool = False
    on_glp1_agonist: bool = False
    has_contrast_allergy: bool = False
    egfr_value: EGFR | None = None
    has_metal_implant: bool = False


class PatientCreate(ConditionFlags):
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    date_of_birth: dt.date
    phone: E164Phone | None = None
    email: EmailStr | None = None
    mrn: Identifier | None = None
    preferred_language: LanguageCode = "en"
    preferred_channel: MessageChannel = MessageChannel.SMS
    consent_to_message: bool = False


class PatientUpdate(BaseModel):
    """Partial update: only fields that are present are changed."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    date_of_birth: dt.date | None = None
    phone: E164Phone | None = None
    email: EmailStr | None = None
    mrn: Identifier | None = None
    preferred_language: LanguageCode | None = None
    preferred_channel: MessageChannel | None = None
    consent_to_message: bool | None = None
    on_anticoagulant: bool | None = None
    diabetic_on_insulin: bool | None = None
    on_glp1_agonist: bool | None = None
    has_contrast_allergy: bool | None = None
    egfr_value: EGFR | None = None
    has_metal_implant: bool | None = None


class PatientSearch(BaseModel):
    """Exact-match search on encrypted identifiers. Sent in the body to keep PHI out of URLs."""

    model_config = ConfigDict(extra="forbid")

    phone: E164Phone | None = None
    email: EmailStr | None = None
    mrn: Identifier | None = None


class PatientOut(ConditionFlags):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: dt.date
    phone: str | None
    email: str | None
    mrn: str | None
    preferred_language: str
    preferred_channel: MessageChannel
    consent_to_message: bool
    consent_timestamp: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


class MagicLinkOut(BaseModel):
    url: str
    expires_at: dt.datetime


class MagicLinkRedeem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, StringConstraints(min_length=20, max_length=200)]


class PatientSessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: dt.datetime


class PatientSelfOut(BaseModel):
    """What a patient sees about themselves in the portal."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    preferred_language: str
    preferred_channel: MessageChannel
    consent_to_message: bool
    hospital_name: str
