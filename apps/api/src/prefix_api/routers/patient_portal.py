"""Endpoints used by patients themselves (authenticated with a magic-link session)."""

from fastapi import APIRouter, Depends

from prefix_api.api.deps import CurrentPatient, DbSession, Now, SettingsDep, patient_data_route
from prefix_api.schemas.patients import MagicLinkRedeem, PatientSelfOut, PatientSessionOut
from prefix_api.services.patient_access import PatientAccessService

router = APIRouter(prefix="/patient", tags=["patient portal"])


@router.post("/session")
def redeem_magic_link(
    body: MagicLinkRedeem, session: DbSession, settings: SettingsDep, now: Now
) -> PatientSessionOut:
    """Exchange a single-use magic-link token (sent in the body, never the URL)."""
    result = PatientAccessService(session, settings).redeem_magic_link(body.token, now=now)
    return PatientSessionOut(access_token=result.access_token, expires_at=result.expires_at)


@router.get("/me", dependencies=[Depends(patient_data_route)])
def me(principal: CurrentPatient, session: DbSession, settings: SettingsDep) -> PatientSelfOut:
    patient = PatientAccessService(session, settings).get_self(principal)
    return PatientSelfOut.model_validate(patient)
