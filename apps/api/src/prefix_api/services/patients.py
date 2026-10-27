"""Patient records. Every read and write is audit-logged (safety rule d)."""

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from prefix_api.core.crypto import (
    get_blind_indexer,
    normalize_email,
    normalize_identifier,
    normalize_phone,
)
from prefix_api.db.models import Patient
from prefix_api.domain.enums import AuditAction
from prefix_api.domain.errors import NotFoundError, ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import patients as patients_repo
from prefix_api.schemas.patients import PatientCreate, PatientSearch, PatientUpdate
from prefix_api.services._db import flush_or_conflict
from prefix_api.services.audit import record_audit

ENTITY = "patient"
_MAX_PAGE_SIZE = 100
_MRN_CONFLICT = "A patient with this MRN already exists"


def _phone_index(phone: str | None) -> str | None:
    return None if phone is None else get_blind_indexer().index(normalize_phone(phone), "phone")


def _email_index(email: str | None) -> str | None:
    return None if email is None else get_blind_indexer().index(normalize_email(email), "email")


def _mrn_index(mrn: str | None) -> str | None:
    return None if mrn is None else get_blind_indexer().index(normalize_identifier(mrn), "mrn")


class PatientService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, principal: StaffPrincipal, data: PatientCreate, *, now: dt.datetime
    ) -> Patient:
        principal.require(Permission.PATIENT_WRITE)
        patient = Patient(
            organization_id=principal.organization_id,
            **data.model_dump(exclude={"phone", "email", "mrn"}),
        )
        self._apply_identifiers(patient, phone=data.phone, email=data.email, mrn=data.mrn)
        patient.consent_timestamp = now if data.consent_to_message else None
        flush_or_conflict(self._session, _MRN_CONFLICT, patient)
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type=ENTITY,
            entity_id=patient.id,
            patient_id=patient.id,
            purpose="patient_registration",
        )
        return patient

    def get(self, principal: StaffPrincipal, patient_id: uuid.UUID, *, purpose: str) -> Patient:
        principal.require(Permission.PATIENT_READ)
        patient = patients_repo.get_patient(self._session, principal.organization_id, patient_id)
        if patient is None:
            raise NotFoundError("Patient not found")
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type=ENTITY,
            entity_id=patient.id,
            patient_id=patient.id,
            purpose=purpose,
        )
        return patient

    def list_patients(
        self, principal: StaffPrincipal, *, limit: int, offset: int, purpose: str
    ) -> list[Patient]:
        principal.require(Permission.PATIENT_READ)
        patients = patients_repo.search_patients(
            self._session,
            principal.organization_id,
            limit=min(limit, _MAX_PAGE_SIZE),
            offset=offset,
        )
        self._audit_listed(principal, patients, purpose)
        return patients

    def search(
        self, principal: StaffPrincipal, query: PatientSearch, *, purpose: str
    ) -> list[Patient]:
        principal.require(Permission.PATIENT_READ)
        if query.phone is None and query.email is None and query.mrn is None:
            raise ValidationFailedError("Provide at least one of phone, email or mrn")
        patients = patients_repo.search_patients(
            self._session,
            principal.organization_id,
            phone_bidx=_phone_index(query.phone),
            email_bidx=_email_index(query.email),
            mrn_bidx=_mrn_index(query.mrn),
        )
        self._audit_listed(
            principal,
            patients,
            purpose,
            query=sorted(field for field, value in query.model_dump().items() if value),
        )
        return patients

    def update(
        self,
        principal: StaffPrincipal,
        patient_id: uuid.UUID,
        data: PatientUpdate,
        *,
        now: dt.datetime,
    ) -> Patient:
        principal.require(Permission.PATIENT_WRITE)
        patient = patients_repo.get_patient(self._session, principal.organization_id, patient_id)
        if patient is None:
            raise NotFoundError("Patient not found")

        changes = data.model_dump(exclude_unset=True)
        identifier_fields = {"phone", "email", "mrn"} & changes.keys()
        for field, value in changes.items():
            if field not in identifier_fields:
                setattr(patient, field, value)
        if identifier_fields:
            self._apply_identifiers(
                patient,
                phone=changes.get("phone", patient.phone),
                email=changes.get("email", patient.email),
                mrn=changes.get("mrn", patient.mrn),
            )
        if "consent_to_message" in changes:
            # Records when consent was given or withdrawn.
            patient.consent_timestamp = now
        flush_or_conflict(self._session, _MRN_CONFLICT)
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.UPDATE,
            entity_type=ENTITY,
            entity_id=patient.id,
            patient_id=patient.id,
            purpose="patient_update",
            details={"fields": sorted(changes)},
        )
        return patient

    def _apply_identifiers(
        self, patient: Patient, *, phone: str | None, email: str | None, mrn: str | None
    ) -> None:
        patient.phone = normalize_phone(phone) if phone else None
        patient.email = normalize_email(email) if email else None
        patient.mrn = mrn
        patient.phone_bidx = _phone_index(phone)
        patient.email_bidx = _email_index(email)
        patient.mrn_bidx = _mrn_index(mrn)

    def _audit_listed(
        self,
        principal: StaffPrincipal,
        patients: list[Patient],
        purpose: str,
        query: list[str] | None = None,
    ) -> None:
        for patient in patients:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.LIST,
                entity_type=ENTITY,
                entity_id=patient.id,
                patient_id=patient.id,
                purpose=purpose,
                details={"query": query} if query else None,
            )
        if not patients:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.LIST,
                entity_type=ENTITY,
                purpose=purpose,
                details={"count": 0, "query": query} if query else {"count": 0},
            )
