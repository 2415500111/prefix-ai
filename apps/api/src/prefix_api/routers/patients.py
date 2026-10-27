import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from prefix_api.api.deps import DbSession, Now, SettingsDep, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.patients import (
    MagicLinkOut,
    PatientCreate,
    PatientOut,
    PatientSearch,
    PatientUpdate,
)
from prefix_api.services.patient_access import PatientAccessService
from prefix_api.services.patients import PatientService

router = APIRouter(
    prefix="/patients", tags=["patients"], dependencies=[Depends(patient_data_route)]
)

Reader = Annotated[StaffPrincipal, Depends(require(Permission.PATIENT_READ))]
Writer = Annotated[StaffPrincipal, Depends(require(Permission.PATIENT_WRITE))]
LinkIssuer = Annotated[StaffPrincipal, Depends(require(Permission.PATIENT_MAGIC_LINK))]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(
    body: PatientCreate, principal: Writer, session: DbSession, now: Now
) -> PatientOut:
    return PatientOut.model_validate(PatientService(session).create(principal, body, now=now))


@router.get("")
def list_patients(
    principal: Reader,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PatientOut]:
    patients = PatientService(session).list_patients(
        principal, limit=limit, offset=offset, purpose="patient_list"
    )
    return [PatientOut.model_validate(p) for p in patients]


@router.post("/search")
def search_patients(body: PatientSearch, principal: Reader, session: DbSession) -> list[PatientOut]:
    patients = PatientService(session).search(principal, body, purpose="patient_search")
    return [PatientOut.model_validate(p) for p in patients]


@router.get("/{patient_id}")
def get_patient(patient_id: uuid.UUID, principal: Reader, session: DbSession) -> PatientOut:
    patient = PatientService(session).get(principal, patient_id, purpose="patient_view")
    return PatientOut.model_validate(patient)


@router.patch("/{patient_id}")
def update_patient(
    patient_id: uuid.UUID, body: PatientUpdate, principal: Writer, session: DbSession, now: Now
) -> PatientOut:
    patient = PatientService(session).update(principal, patient_id, body, now=now)
    return PatientOut.model_validate(patient)


@router.post("/{patient_id}/magic-links", status_code=status.HTTP_201_CREATED)
def issue_magic_link(
    patient_id: uuid.UUID,
    principal: LinkIssuer,
    session: DbSession,
    settings: SettingsDep,
    now: Now,
) -> MagicLinkOut:
    link = PatientAccessService(session, settings).issue_magic_link(principal, patient_id, now=now)
    return MagicLinkOut(url=link.url, expires_at=link.expires_at)
