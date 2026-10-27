from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    NURSE = "NURSE"
    CLINICIAN = "CLINICIAN"
    VIEWER = "VIEWER"


class MessageChannel(StrEnum):
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    PORTAL = "PORTAL"


class AppointmentStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    READY = "READY"
    AT_RISK = "AT_RISK"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class CancellationReason(StrEnum):
    INADEQUATE_BOWEL_PREP = "INADEQUATE_BOWEL_PREP"
    ATE_OR_DRANK = "ATE_OR_DRANK"
    MEDICATION_NOT_STOPPED = "MEDICATION_NOT_STOPPED"
    NO_ESCORT = "NO_ESCORT"
    MISSING_LABS = "MISSING_LABS"
    MISSING_PAPERWORK = "MISSING_PAPERWORK"
    PATIENT_NO_SHOW = "PATIENT_NO_SHOW"
    PATIENT_REQUESTED = "PATIENT_REQUESTED"
    CLINICAL_REASON = "CLINICAL_REASON"
    FACILITY_OR_STAFF = "FACILITY_OR_STAFF"
    OTHER = "OTHER"

    @property
    def is_prep_related(self) -> bool:
        return self in _PREP_RELATED_REASONS


_PREP_RELATED_REASONS = frozenset(
    {
        CancellationReason.INADEQUATE_BOWEL_PREP,
        CancellationReason.ATE_OR_DRANK,
        CancellationReason.MEDICATION_NOT_STOPPED,
        CancellationReason.NO_ESCORT,
        CancellationReason.MISSING_LABS,
        CancellationReason.MISSING_PAPERWORK,
    }
)


class ProtocolStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


class StepCategory(StrEnum):
    DIET = "DIET"
    FASTING = "FASTING"
    MEDICATION = "MEDICATION"
    BOWEL_PREP = "BOWEL_PREP"
    LAB = "LAB"
    LOGISTICS = "LOGISTICS"
    PAPERWORK = "PAPERWORK"


class TimelineEventStatus(StrEnum):
    PENDING = "PENDING"
    # Claimed by a dispatcher; a reminder is being sent. Never re-sent automatically.
    SENDING = "SENDING"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    MISSED = "MISSED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class CheckInStatus(StrEnum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    EXPIRED = "EXPIRED"


class CheckInResponse(StrEnum):
    YES = "YES"
    NO = "NO"
    HELP = "HELP"
    OTHER = "OTHER"


class MessageDirection(StrEnum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class MessageStatus(StrEnum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RECEIVED = "RECEIVED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WaitlistStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OFFERED = "OFFERED"
    BOOKED = "BOOKED"
    REMOVED = "REMOVED"


class EscalationSource(StrEnum):
    RED_FLAG = "RED_FLAG"
    OUT_OF_PROTOCOL = "OUT_OF_PROTOCOL"
    PATIENT_REPORTED_PROBLEM = "PATIENT_REPORTED_PROBLEM"
    HIGH_RISK = "HIGH_RISK"
    STAFF = "STAFF"


class EscalationSeverity(StrEnum):
    URGENT = "URGENT"
    HIGH = "HIGH"
    NORMAL = "NORMAL"


class EscalationStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskType(StrEnum):
    CALL_PATIENT = "CALL_PATIENT"
    CONFIRM_ESCORT = "CONFIRM_ESCORT"
    REVIEW_RISK = "REVIEW_RISK"
    RESCHEDULE = "RESCHEDULE"
    BACKFILL_SLOT = "BACKFILL_SLOT"
    NURSE_REVIEW = "NURSE_REVIEW"
    OTHER = "OTHER"


class ActorType(StrEnum):
    USER = "USER"
    PATIENT = "PATIENT"
    SYSTEM = "SYSTEM"
    ANONYMOUS = "ANONYMOUS"


class AuditAction(StrEnum):
    READ = "READ"
    LIST = "LIST"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXPORT = "EXPORT"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"
    MAGIC_LINK_ISSUED = "MAGIC_LINK_ISSUED"
    MAGIC_LINK_REDEEMED = "MAGIC_LINK_REDEEMED"
    MAGIC_LINK_REJECTED = "MAGIC_LINK_REJECTED"
