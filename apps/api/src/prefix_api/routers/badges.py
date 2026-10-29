"""Sidebar counts. Totals only, so this router is not marked as handling patient data."""

from typing import Annotated

from fastapi import APIRouter, Depends

from prefix_api.api.deps import DbSession, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.requests import BadgesOut
from prefix_api.services.badges import BadgeService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Reader = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_READ))]


@router.get("/badges")
def badges(principal: Reader, session: DbSession) -> BadgesOut:
    counts = BadgeService(session).counts(principal)
    return BadgesOut(
        open_tasks=counts.open_tasks,
        open_escalations=counts.open_escalations,
        pending_requests=counts.pending_requests,
    )
