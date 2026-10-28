"""Create throwaway patient-portal data for the Playwright end-to-end tests.

Each run creates a fresh organization (so runs never interfere) with an approved protocol,
three patients with an appointment two days out, and one magic link each. Prints JSON:
{"en": "<link>", "hi": "<link>", "reuse": "<link>"}.

Development and CI only: refuses to run against production.
"""

import datetime as dt
import json
import secrets
from decimal import Decimal

from prefix_api.core.config import get_settings
from prefix_api.core.crypto import configure_crypto
from prefix_api.core.security import hash_password
from prefix_api.db.models import Facility, Organization, ProcedureType, User
from prefix_api.db.session import create_db_engine, create_session_factory
from prefix_api.domain.enums import MessageChannel, Role, StepCategory
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.schemas.patients import PatientCreate
from prefix_api.schemas.protocols import ProtocolIn, StepIn
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.embeddings import get_embedding_provider
from prefix_api.services.patient_access import PatientAccessService
from prefix_api.services.patients import PatientService
from prefix_api.services.protocols import ProtocolService

DAY = 24 * 60
STEPS = [
    # Applies from 3 days before: "in effect" now.
    StepIn(
        offset_minutes=3 * DAY,
        title="Low-fibre diet",
        instruction_text="Eat low-fibre food until the day before your procedure.",
        category=StepCategory.DIET,
    ),
    # Due an hour ago: within the confirmation grace period, so "Do this now".
    StepIn(
        offset_minutes=2 * DAY,
        title="Arrange an escort",
        instruction_text="Ask an adult to take you home after the procedure.",
        category=StepCategory.LOGISTICS,
        requires_confirmation=True,
    ),
    # Tomorrow: "Coming up", and a problem can be reported already.
    StepIn(
        offset_minutes=1 * DAY,
        title="Clear liquids only",
        instruction_text="From now on, have clear liquids only.",
        category=StepCategory.DIET,
        requires_confirmation=True,
        is_critical=True,
    ),
]
PATIENTS = {"en": ("Asha", "en"), "hi": ("Ravi", "hi"), "reuse": ("Meera", "en")}


def main() -> None:
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to create test data in production.")
    configure_crypto(settings)
    now = dt.datetime.now(dt.UTC)
    engine = create_db_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            suffix = secrets.token_hex(4)
            org = Organization(
                name=f"E2E Hospital {suffix}",
                slug=f"e2e-{suffix}",
                country_code="IN",
                default_timezone="Asia/Kolkata",
            )
            session.add(org)
            session.flush()
            facility = Facility(
                organization_id=org.id,
                name="E2E Main Campus",
                timezone="Asia/Kolkata",
                address="1 Test Road, Bengaluru",
                maps_url="https://maps.example.com/e2e",
                phone="+911100000000",
            )
            procedure = ProcedureType(
                organization_id=org.id,
                code="COLONOSCOPY",
                name="Colonoscopy",
                default_duration_minutes=45,
                or_cost_per_minute=Decimal("150.00"),
                requires_sedation=True,
            )
            users = {
                role: User(
                    organization_id=org.id,
                    email=f"{role.value.lower()}-{suffix}@e2e.example.com",
                    full_name=f"E2E {role.value.title()}",
                    role=role,
                    password_hash=hash_password(secrets.token_urlsafe(16)),
                )
                for role in (Role.CLINICIAN, Role.COORDINATOR)
            }
            session.add_all([facility, procedure, *users.values()])
            session.flush()
            clinician, coordinator = (
                StaffPrincipal(user_id=u.id, organization_id=org.id, role=u.role)
                for u in users.values()
            )

            protocols = ProtocolService(session, get_embedding_provider("local"))
            protocol = protocols.create(
                clinician,
                ProtocolIn(procedure_type_id=procedure.id, name="E2E prep", steps=STEPS),
            )
            protocols.approve(clinician, protocol.id, acknowledge_sample=False, now=now)

            scheduled_at = now + dt.timedelta(days=2, hours=-1)
            links = {}
            for key, (first_name, language) in PATIENTS.items():
                patient = PatientService(session).create(
                    coordinator,
                    PatientCreate(
                        first_name=first_name,
                        last_name="Test",
                        date_of_birth=dt.date(1980, 1, 1),
                        preferred_language=language,
                        preferred_channel=MessageChannel.PORTAL,
                    ),
                    now=now,
                )
                session.flush()
                AppointmentService(session).create(
                    coordinator,
                    AppointmentCreate(
                        patient_id=patient.id,
                        facility_id=facility.id,
                        procedure_type_id=procedure.id,
                        scheduled_at=scheduled_at,
                        arrival_at=scheduled_at - dt.timedelta(hours=1),
                    ),
                    now=now,
                )
                link = PatientAccessService(session, settings).issue_magic_link(
                    coordinator, patient.id, now=now
                )
                links[key] = link.url
            session.commit()
    finally:
        engine.dispose()
    # Last line of output: the test runner parses it (logs may come before it).
    print(json.dumps(links))


if __name__ == "__main__":
    main()
