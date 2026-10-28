import dataclasses
import datetime as dt
from decimal import Decimal

from pydantic import BaseModel

from prefix_api.services.analytics import Summary


class AnalyticsSummaryOut(BaseModel):
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
    # Estimates need a baseline rate from the hospital; without one they are null.
    baseline_rate: float | None
    avoided_estimate: int | None
    or_minutes_saved_estimate: int | None
    or_cost_saved_estimate: Decimal | None

    @classmethod
    def from_summary(cls, summary: Summary) -> AnalyticsSummaryOut:
        return cls(**dataclasses.asdict(summary))
