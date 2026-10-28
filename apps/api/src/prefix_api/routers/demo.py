"""Guest demo: reset the synthetic data, and open a fresh link to one of its patients."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from prefix_api.api.deps import DbSession, Now, SettingsDep, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.demo import DemoPatientLinkOut, DemoResetOut
from prefix_api.services.demo import demo_patient_link, reset_demo_for

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(patient_data_route)])

Resetter = Annotated[StaffPrincipal, Depends(require(Permission.DEMO_RESET))]
Reader = Annotated[StaffPrincipal, Depends(require(Permission.PATIENT_READ))]


@router.post("/reset")
def reset_demo(principal: Resetter, request: Request, now: Now) -> DemoResetOut:
    """Admin-only, and only for the demo hospital's own admin. Also runs every night."""
    result = reset_demo_for(principal, request.app.state.session_factory, now=now)
    return DemoResetOut(
        patients=result.patients,
        appointments=result.appointments,
        reminders_sent=result.reminders_sent,
        answers=result.answers,
        escalations=result.escalations,
    )


@router.post("/patient-link")
def open_demo_patient(
    principal: Reader,
    session: DbSession,
    settings: SettingsDep,
    now: Now,
    lang: Literal["en", "hi"] = "en",
) -> DemoPatientLinkOut:
    url, name = demo_patient_link(session, settings, language=lang, now=now)
    return DemoPatientLinkOut(url=url, patient_name=name, language=lang)
