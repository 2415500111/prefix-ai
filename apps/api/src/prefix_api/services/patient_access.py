"""Patient access via single-use magic links, and the patient's view of their own record."""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.core.security import hash_opaque_token, issue_patient_token, new_opaque_token
from prefix_api.db.models import Patient, PatientMagicLink
from prefix_api.domain.enums import AuditAction
from prefix_api.domain.errors import AuthenticationError, NotFoundError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import PatientPrincipal, StaffPrincipal
from prefix_api.repositories import patients as patients_repo
from prefix_api.services.audit import record_audit


@dataclass(frozen=True, slots=True)
class IssuedMagicLink:
    url: str
    expires_at: dt.datetime


@dataclass(frozen=True, slots=True)
class PatientSession:
    access_token: str
    expires_at: dt.datetime


class PatientAccessService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def issue_magic_link(
        self, principal: StaffPrincipal, patient_id: uuid.UUID, *, now: dt.datetime
    ) -> IssuedMagicLink:
        principal.require(Permission.PATIENT_MAGIC_LINK)
        patient = patients_repo.get_patient(self._session, principal.organization_id, patient_id)
        if patient is None:
            raise NotFoundError("Patient not found")

        token = new_opaque_token()
        expires_at = now + dt.timedelta(minutes=self._settings.magic_link_ttl_minutes)
        link = PatientMagicLink(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            token_hash=hash_opaque_token(token),
            created_at=now,
            expires_at=expires_at,
            created_by_user_id=principal.user_id,
        )
        patients_repo.add_magic_link(self._session, link)
        self._session.flush()
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.MAGIC_LINK_ISSUED,
            entity_type="patient_magic_link",
            entity_id=link.id,
            patient_id=patient.id,
            purpose="patient_portal_access",
        )
        # The token travels in the URL fragment, which browsers never send to servers,
        # so it cannot end up in web server or proxy logs.
        base = str(self._settings.web_base_url).rstrip("/")
        return IssuedMagicLink(url=f"{base}/p#token={token}", expires_at=expires_at)

    def redeem_magic_link(self, token: str, *, now: dt.datetime) -> PatientSession:
        link = patients_repo.consume_magic_link(self._session, hash_opaque_token(token), now)
        if link is None:
            record_audit(
                self._session,
                principal=None,
                action=AuditAction.MAGIC_LINK_REJECTED,
                entity_type="patient_magic_link",
                purpose="patient_portal_access",
            )
            self._session.commit()
            raise AuthenticationError("This link is invalid, expired or already used")

        principal = PatientPrincipal(
            patient_id=link.patient_id, organization_id=link.organization_id
        )
        access_token, expires_at = issue_patient_token(
            self._settings,
            patient_id=link.patient_id,
            organization_id=link.organization_id,
            now=now,
        )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.MAGIC_LINK_REDEEMED,
            entity_type="patient_magic_link",
            entity_id=link.id,
            patient_id=link.patient_id,
            purpose="patient_portal_access",
        )
        return PatientSession(access_token=access_token, expires_at=expires_at)

    def get_self(self, principal: PatientPrincipal) -> Patient:
        patient = patients_repo.get_patient(
            self._session, principal.organization_id, principal.patient_id
        )
        if patient is None:
            raise AuthenticationError("Patient session is no longer valid")
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="patient",
            entity_id=patient.id,
            patient_id=patient.id,
            purpose="patient_self_access",
        )
        return patient
