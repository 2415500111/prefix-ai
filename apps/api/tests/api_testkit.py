"""Shared test helpers: settings, data builders and auth headers."""

import base64
import datetime as dt
import os
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.core.crypto import get_blind_indexer, normalize_email, normalize_phone
from prefix_api.core.security import hash_password, issue_access_token, issue_patient_token
from prefix_api.db.models import (
    Facility,
    Organization,
    Patient,
    PrepProtocol,
    PrepStep,
    ProcedureType,
    User,
)
from prefix_api.domain.enums import ProtocolStatus, Role, StepCategory

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://prefix:prefix@localhost:5432/prefix_test"
)
TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-chars"
# Fixed, non-secret keys so test runs are reproducible.
TEST_KEY_ACTIVE = "test2:" + base64.urlsafe_b64encode(bytes(range(32, 64))).decode()
TEST_KEY_OLD = "test1:" + base64.urlsafe_b64encode(bytes(range(32))).decode()
TEST_BLIND_INDEX_KEY = "test-blind-index-key-at-least-32-characters"
PASSWORD = "correct horse battery staple"


def make_test_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "llm_model": "test-model",
        "jwt_secret": TEST_JWT_SECRET,
        "cors_origins": ["http://localhost:3000"],
        "pii_encryption_keys": [TEST_KEY_ACTIVE, TEST_KEY_OLD],
        "pii_blind_index_key": TEST_BLIND_INDEX_KEY,
        "database_url": TEST_DATABASE_URL,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True)
class StepSpec:
    offset_minutes: int
    title: str
    is_critical: bool = False
    requires_confirmation: bool = False
    conditions: dict[str, Any] | None = None
    category: StepCategory = StepCategory.DIET


class Builder:
    """Creates rows directly through the ORM (bypassing services and their audit rows)."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._counter = 0

    def _next(self) -> int:
        self._counter += 1
        return self._counter

    def organization(self, name: str = "Org") -> Organization:
        n = self._next()
        org = Organization(
            name=f"{name} {n}",
            slug=f"org-{n}-{os.urandom(3).hex()}",
            country_code="IN",
            default_timezone="Asia/Kolkata",
        )
        self.session.add(org)
        self.session.flush()
        return org

    def facility(self, org: Organization, timezone: str = "Asia/Kolkata") -> Facility:
        facility = Facility(
            organization_id=org.id, name=f"Facility {self._next()}", timezone=timezone
        )
        self.session.add(facility)
        self.session.flush()
        return facility

    def procedure_type(self, org: Organization, code: str = "COLONOSCOPY") -> ProcedureType:
        procedure_type = ProcedureType(
            organization_id=org.id,
            code=code,
            name=code.title(),
            default_duration_minutes=45,
            or_cost_per_minute=50,
        )
        self.session.add(procedure_type)
        self.session.flush()
        return procedure_type

    def approved_protocol(
        self,
        org: Organization,
        procedure_type: ProcedureType,
        steps: list[StepSpec],
        *,
        name: str = "Prep",
    ) -> PrepProtocol:
        approver = self.user(org, Role.CLINICIAN)
        protocol = PrepProtocol(
            organization_id=org.id,
            family_id=uuid.uuid7(),
            version=1,
            procedure_type_id=procedure_type.id,
            name=name,
            steps=[
                PrepStep(
                    organization_id=org.id,
                    sort_order=index,
                    offset_minutes=spec.offset_minutes,
                    title=spec.title,
                    instruction_text=f"Instruction for {spec.title}.",
                    category=spec.category,
                    is_critical=spec.is_critical,
                    requires_confirmation=spec.requires_confirmation,
                    conditions=spec.conditions,
                )
                for index, spec in enumerate(steps)
            ],
        )
        self.session.add(protocol)
        self.session.flush()
        protocol.status = ProtocolStatus.APPROVED
        protocol.approved_by_id = approver.id
        protocol.approved_at = utcnow()
        self.session.flush()
        return protocol

    def user(self, org: Organization, role: Role = Role.ADMIN, *, active: bool = True) -> User:
        user = User(
            organization_id=org.id,
            email=f"user{self._next()}-{os.urandom(3).hex()}@example.com",
            full_name="Test User",
            role=role,
            password_hash=hash_password(PASSWORD),
            is_active=active,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def patient(self, org: Organization, **fields: Any) -> Patient:
        n = self._next()
        phone = fields.pop("phone", f"+9198765{n:05d}")
        email = fields.pop("email", f"patient{n}@example.com")
        indexer = get_blind_indexer()
        patient = Patient(
            organization_id=org.id,
            first_name=fields.pop("first_name", "Asha"),
            last_name=fields.pop("last_name", f"Patient{n}"),
            date_of_birth=fields.pop("date_of_birth", dt.date(1970, 1, 1)),
            phone=phone,
            email=email,
            phone_bidx=indexer.index(normalize_phone(phone), "phone"),
            email_bidx=indexer.index(normalize_email(email), "email"),
            **fields,
        )
        self.session.add(patient)
        self.session.flush()
        return patient


def staff_headers(settings: Settings, user: User) -> dict[str, str]:
    token, _ = issue_access_token(
        settings,
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        now=utcnow(),
    )
    return {"Authorization": f"Bearer {token}"}


def patient_headers(settings: Settings, patient: Patient) -> dict[str, str]:
    token, _ = issue_patient_token(
        settings, patient_id=patient.id, organization_id=patient.organization_id, now=utcnow()
    )
    return {"Authorization": f"Bearer {token}"}
