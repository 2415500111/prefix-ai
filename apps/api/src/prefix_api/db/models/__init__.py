"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from prefix_api.db.models.assistant import AssistantExchange
from prefix_api.db.models.audit import AuditLog
from prefix_api.db.models.engagement import (
    CheckIn,
    Message,
    PatientNotificationRead,
    PatientTimelineEvent,
)
from prefix_api.db.models.operations import (
    BackfillOffer,
    Escalation,
    RiskScore,
    Task,
    WaitlistEntry,
)
from prefix_api.db.models.organization import Facility, Organization
from prefix_api.db.models.patient import Patient, PatientMagicLink
from prefix_api.db.models.protocol import PrepProtocol, PrepStep, PrepStepTranslation
from prefix_api.db.models.scheduling import Appointment, ProcedureType
from prefix_api.db.models.user import RefreshToken, User

__all__ = [
    "Appointment",
    "AssistantExchange",
    "AuditLog",
    "BackfillOffer",
    "CheckIn",
    "Escalation",
    "Facility",
    "Message",
    "Organization",
    "Patient",
    "PatientMagicLink",
    "PatientNotificationRead",
    "PatientTimelineEvent",
    "PrepProtocol",
    "PrepStep",
    "PrepStepTranslation",
    "ProcedureType",
    "RefreshToken",
    "RiskScore",
    "Task",
    "User",
    "WaitlistEntry",
]
