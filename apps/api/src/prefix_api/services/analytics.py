"""Analytics: how often procedures are cancelled, why, and what that cost in theatre time.

Definitions are deliberate and printed on the page:

- A procedure is counted in the range when it is scheduled inside it (UTC dates).
- Prep-related cancellations are those with a reason the patient could have prevented.
- OR minutes and OR cost "at risk" are what the prep-related cancellations cost. This is
  exposure, not savings.
- "Avoided" cancellations are only estimated against a baseline rate the hospital supplies
  (its cancellation rate before Prefix AI). Without a baseline nothing is claimed as saved.
- Slots backfilled needs the waitlist (Phase 9); it is not reported until then.
"""

import csv
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Appointment, CheckIn, ProcedureType
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    CancellationReason,
    CheckInStatus,
)
from prefix_api.domain.errors import ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.services.audit import record_audit

PREP_REASONS = frozenset(
    {
        CancellationReason.INADEQUATE_BOWEL_PREP,
        CancellationReason.ATE_OR_DRANK,
        CancellationReason.MEDICATION_NOT_STOPPED,
        CancellationReason.NO_ESCORT,
        CancellationReason.MISSING_LABS,
        CancellationReason.MISSING_PAPERWORK,
    }
)
MAX_RANGE = dt.timedelta(days=366)


@dataclass(frozen=True, slots=True)
class Summary:
    start: dt.date
    end: dt.date
    procedures: int
    cancelled: int
    cancellation_rate: float | None
    prep_cancelled: int
    prep_share: float | None
    checkins_sent: int
    checkins_answered: int
    response_rate: float | None
    or_minutes_at_risk: int
    or_cost_at_risk: Decimal
    baseline_rate: float | None
    avoided_estimate: int | None
    or_minutes_saved_estimate: int | None
    or_cost_saved_estimate: Decimal | None


def _percent(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _range(start: dt.date, end: dt.date) -> tuple[dt.datetime, dt.datetime]:
    if end < start:
        raise ValidationFailedError("The end date is before the start date")
    if end - start > MAX_RANGE:
        raise ValidationFailedError("Choose a range of one year or less")
    begin = dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC)
    finish = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC)
    return begin, finish


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(
        self,
        principal: StaffPrincipal,
        *,
        start: dt.date,
        end: dt.date,
        baseline_rate: float | None,
    ) -> Summary:
        principal.require(Permission.ANALYTICS_READ)
        begin, finish = _range(start, end)
        rows = self._session.execute(
            select(Appointment, ProcedureType)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.scheduled_at >= begin,
                Appointment.scheduled_at < finish,
            )
        ).all()
        procedures = len(rows)
        cancelled = [(a, p) for a, p in rows if a.status is AppointmentStatus.CANCELLED]
        prep = [(a, p) for a, p in cancelled if a.cancellation_reason in PREP_REASONS]
        at_risk_minutes = sum(a.duration_minutes for a, _ in prep)
        at_risk_cost = sum(
            (Decimal(a.duration_minutes) * p.or_cost_per_minute for a, p in prep), Decimal(0)
        )

        sent, answered = self._checkin_counts(principal, begin, finish)

        avoided: int | None = None
        minutes_saved: int | None = None
        cost_saved: Decimal | None = None
        if baseline_rate is not None and procedures:
            expected_cancelled = baseline_rate / 100 * procedures
            avoided = max(0, round(expected_cancelled - len(cancelled)))
            average_minutes = sum(a.duration_minutes for a, _ in rows) / procedures
            average_cost = (
                sum(
                    (Decimal(a.duration_minutes) * p.or_cost_per_minute for a, p in rows),
                    Decimal(0),
                )
                / procedures
            )
            minutes_saved = round(avoided * average_minutes)
            cost_saved = (Decimal(avoided) * average_cost).quantize(Decimal("0.01"))

        result = Summary(
            start=start,
            end=end,
            procedures=procedures,
            cancelled=len(cancelled),
            cancellation_rate=_percent(len(cancelled), procedures),
            prep_cancelled=len(prep),
            prep_share=_percent(len(prep), len(cancelled)),
            checkins_sent=sent,
            checkins_answered=answered,
            response_rate=_percent(answered, sent),
            or_minutes_at_risk=at_risk_minutes,
            or_cost_at_risk=at_risk_cost.quantize(Decimal("0.01")),
            baseline_rate=baseline_rate,
            avoided_estimate=avoided,
            or_minutes_saved_estimate=minutes_saved,
            or_cost_saved_estimate=cost_saved,
        )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="analytics",
            purpose="analytics_summary",
            details={"count": procedures},
        )
        return result

    def export_csv(self, principal: StaffPrincipal, *, start: dt.date, end: dt.date) -> str:
        """One row per procedure in the range. No names: only ids, times and outcomes."""
        principal.require(Permission.ANALYTICS_EXPORT)
        begin, finish = _range(start, end)
        rows = self._session.execute(
            select(Appointment, ProcedureType)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.scheduled_at >= begin,
                Appointment.scheduled_at < finish,
            )
            .order_by(Appointment.scheduled_at)
        ).all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "appointment_id",
                "scheduled_at_utc",
                "procedure_code",
                "status",
                "cancellation_reason",
                "duration_minutes",
                "or_cost",
            ]
        )
        for appointment, procedure in rows:
            writer.writerow(
                [
                    appointment.id,
                    appointment.scheduled_at.astimezone(dt.UTC).isoformat(),
                    procedure.code,
                    appointment.status.value,
                    appointment.cancellation_reason.value
                    if appointment.cancellation_reason
                    else "",
                    appointment.duration_minutes,
                    (Decimal(appointment.duration_minutes) * procedure.or_cost_per_minute).quantize(
                        Decimal("0.01")
                    ),
                ]
            )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.EXPORT,
            entity_type="analytics",
            purpose="analytics_export",
            details={"count": len(rows)},
        )
        return buffer.getvalue()

    def _checkin_counts(
        self, principal: StaffPrincipal, begin: dt.datetime, finish: dt.datetime
    ) -> tuple[int, int]:
        rows = self._session.execute(
            select(CheckIn.status)
            .join(Appointment, Appointment.id == CheckIn.appointment_id)
            .where(
                CheckIn.organization_id == principal.organization_id,
                CheckIn.sent_at.is_not(None),
                Appointment.scheduled_at >= begin,
                Appointment.scheduled_at < finish,
            )
        ).all()
        answered = sum(1 for (status,) in rows if status is CheckInStatus.ANSWERED)
        return len(rows), answered
