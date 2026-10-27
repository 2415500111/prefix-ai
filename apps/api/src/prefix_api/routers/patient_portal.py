"""Endpoints used by patients themselves (authenticated with a magic-link session)."""

import uuid

from fastapi import APIRouter, Depends, Response, status

from prefix_api.api.deps import CurrentPatient, DbSession, Now, SettingsDep, patient_data_route
from prefix_api.schemas.patients import MagicLinkRedeem, PatientSelfOut, PatientSessionOut
from prefix_api.schemas.portal import PortalAppointment, ProblemReport, RescheduleRequest
from prefix_api.services.patient_access import PatientAccessService
from prefix_api.services.portal import PortalService

router = APIRouter(prefix="/patient", tags=["patient portal"])
patient_data = [Depends(patient_data_route)]


@router.post("/session")
def redeem_magic_link(
    body: MagicLinkRedeem, session: DbSession, settings: SettingsDep, now: Now
) -> PatientSessionOut:
    """Exchange a single-use magic-link token (sent in the body, never the URL)."""
    result = PatientAccessService(session, settings).redeem_magic_link(body.token, now=now)
    return PatientSessionOut(access_token=result.access_token, expires_at=result.expires_at)


@router.get("/me", dependencies=patient_data)
def me(principal: CurrentPatient, session: DbSession, settings: SettingsDep) -> PatientSelfOut:
    patient = PatientAccessService(session, settings).get_self(principal)
    return PatientSelfOut.model_validate(patient)


@router.get("/appointments", dependencies=patient_data)
def my_appointments(
    principal: CurrentPatient, session: DbSession, now: Now
) -> list[PortalAppointment]:
    return PortalService(session).list_appointments(principal, now=now)


@router.post(
    "/steps/{event_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def confirm_step(
    event_id: uuid.UUID, principal: CurrentPatient, session: DbSession, now: Now
) -> None:
    PortalService(session).confirm_step(principal, event_id, now=now)


@router.post(
    "/steps/{event_id}/problem",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def report_problem(
    event_id: uuid.UUID,
    body: ProblemReport,
    principal: CurrentPatient,
    session: DbSession,
    now: Now,
) -> None:
    PortalService(session).report_problem(principal, event_id, note=body.note, now=now)


@router.post(
    "/appointments/{appointment_id}/reschedule-request",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def request_reschedule(
    appointment_id: uuid.UUID,
    body: RescheduleRequest,
    principal: CurrentPatient,
    session: DbSession,
    now: Now,
) -> None:
    PortalService(session).request_reschedule(principal, appointment_id, note=body.note, now=now)


@router.get(
    "/appointments/{appointment_id}/calendar.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
    dependencies=patient_data,
)
def calendar(
    appointment_id: uuid.UUID,
    principal: CurrentPatient,
    session: DbSession,
    settings: SettingsDep,
    now: Now,
) -> Response:
    portal_url = f"{str(settings.web_base_url).rstrip('/')}/p/home"
    ics = PortalService(session).calendar(principal, appointment_id, portal_url=portal_url, now=now)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="procedure.ics"',
            "Cache-Control": "no-store",
        },
    )
