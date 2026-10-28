"""Analytics: one summary for a date range, and a CSV export of its procedures."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from prefix_api.api.deps import DbSession, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.analytics import AnalyticsSummaryOut
from prefix_api.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

Reader = Annotated[StaffPrincipal, Depends(require(Permission.ANALYTICS_READ))]
Exporter = Annotated[StaffPrincipal, Depends(require(Permission.ANALYTICS_EXPORT))]
Start = Annotated[dt.date, Query()]
Baseline = Annotated[float | None, Query(ge=0, le=100)]


@router.get("/summary")
def summary(
    principal: Reader,
    session: DbSession,
    start: Start,
    end: Start,
    baseline_rate: Baseline = None,
) -> AnalyticsSummaryOut:
    result = AnalyticsService(session).summary(
        principal, start=start, end=end, baseline_rate=baseline_rate
    )
    return AnalyticsSummaryOut.from_summary(result)


@router.get("/export.csv")
def export_csv(principal: Exporter, session: DbSession, start: Start, end: Start) -> Response:
    body = AnalyticsService(session).export_csv(principal, start=start, end=end)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="procedures-{start}-{end}.csv"',
            "Cache-Control": "no-store",
        },
    )
