import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from prefix_api.domain.enums import EscalationSeverity, EscalationSource, EscalationStatus
from prefix_api.domain.urgency import UrgentReason
from prefix_api.services.escalations import InboxItem

ResolutionNote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class EscalationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    appointment_id: uuid.UUID | None
    procedure_name: str | None
    scheduled_at: dt.datetime | None
    # The facility's time zone, for showing when it was raised (None without a booking).
    timezone: str | None
    source: EscalationSource
    severity: EscalationSeverity
    status: EscalationStatus
    # Written from the patient's own words where they are relevant, for the nurse.
    summary: str
    created_at: dt.datetime
    acknowledged_at: dt.datetime | None
    resolved_at: dt.datetime | None
    resolution_note: str | None
    # Fixed rules (domain.urgency): red flag, critical step, procedure within 24 hours.
    urgent: bool
    urgent_reasons: list[UrgentReason]

    @classmethod
    def from_item(cls, item: InboxItem) -> EscalationOut:
        escalation = item.escalation
        return cls(
            id=escalation.id,
            patient_id=escalation.patient_id,
            patient_name=f"{item.patient.first_name} {item.patient.last_name}",
            appointment_id=escalation.appointment_id,
            procedure_name=item.procedure_name,
            scheduled_at=item.appointment.scheduled_at if item.appointment else None,
            timezone=item.timezone,
            source=escalation.source,
            severity=escalation.severity,
            status=escalation.status,
            summary=escalation.summary,
            created_at=escalation.created_at,
            acknowledged_at=escalation.acknowledged_at,
            resolved_at=escalation.resolved_at,
            resolution_note=escalation.resolution_note,
            urgent=bool(item.urgent_reasons),
            urgent_reasons=list(item.urgent_reasons),
        )


class EscalationResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: ResolutionNote
