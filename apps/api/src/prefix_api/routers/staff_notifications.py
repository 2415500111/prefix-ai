"""Staff notifications: what patients raised, newest first, for the bell and its live updates."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from prefix_api.api.deps import DbSession, Now, StaffUser, patient_data_route
from prefix_api.schemas.staff_notifications import (
    StaffNotificationFeedOut,
    StaffNotificationReadIn,
    StaffNotificationSummaryOut,
)
from prefix_api.services.staff_notifications import MAX_ITEMS, StaffNotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
patient_data = [Depends(patient_data_route)]


@router.get("/summary")
def notification_summary(
    principal: StaffUser, session: DbSession, now: Now
) -> StaffNotificationSummaryOut:
    """Totals and the newest id, cheap enough to poll. Not patient data, so not audited."""
    summary = StaffNotificationService(session).summary(principal, now=now)
    return StaffNotificationSummaryOut.from_summary(summary)


@router.get("", dependencies=patient_data)
def list_notifications(
    principal: StaffUser,
    session: DbSession,
    now: Now,
    urgent_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=MAX_ITEMS)] = MAX_ITEMS,
) -> StaffNotificationFeedOut:
    """Newest first by when the patient raised it; urgency never changes the order."""
    feed = StaffNotificationService(session).feed(
        principal, now=now, urgent_only=urgent_only, limit=limit
    )
    return StaffNotificationFeedOut.from_feed(feed)


@router.post("/read", dependencies=patient_data)
def mark_notifications_read(
    body: StaffNotificationReadIn, principal: StaffUser, session: DbSession, now: Now
) -> StaffNotificationSummaryOut:
    summary = StaffNotificationService(session).mark_read(principal, body.ids, now=now)
    return StaffNotificationSummaryOut.from_summary(summary)


@router.post("/read-all", dependencies=patient_data)
def mark_all_notifications_read(
    principal: StaffUser, session: DbSession, now: Now
) -> StaffNotificationSummaryOut:
    summary = StaffNotificationService(session).mark_all_read(principal, now=now)
    return StaffNotificationSummaryOut.from_summary(summary)
