from typing import Literal

from pydantic import BaseModel


class DemoResetOut(BaseModel):
    patients: int
    appointments: int
    reminders_sent: int
    answers: int
    escalations: int


class DemoPatientLinkOut(BaseModel):
    url: str
    patient_name: str
    language: Literal["en", "hi"]


class CapabilitiesOut(BaseModel):
    guest_login: bool
