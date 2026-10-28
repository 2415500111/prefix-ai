"""CSV imports: dry runs write nothing, a commit writes everything or nothing, and every row
error says what is wrong without repeating the patient's data."""

import datetime as dt
from zoneinfo import ZoneInfo

from api_testkit import Builder, StepSpec, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import Appointment, AuditLog, Facility, Organization, Patient
from prefix_api.domain.enums import AppointmentStatus, Role
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.patients import PatientCreate
from prefix_api.services.patients import PatientService

KOLKATA = ZoneInfo("Asia/Kolkata")
DAY = 24 * 60
STEPS = [StepSpec(3 * DAY, "Clear liquids"), StepSpec(1 * DAY, "Low-fibre diet")]
PATIENT_HEADER = "first_name,last_name,date_of_birth,phone,email,consent_to_message"


class Hospital:
    def __init__(self, build: Builder, session: Session, settings: Settings) -> None:
        self.session = session
        self.org: Organization = build.organization()
        self.facility = Facility(
            organization_id=self.org.id, name="Main Campus", timezone="Asia/Kolkata"
        )
        session.add(self.facility)
        session.flush()
        self.procedure = build.procedure_type(self.org, code="COLONOSCOPY")
        build.approved_protocol(self.org, self.procedure, STEPS)
        coordinator = build.user(self.org, Role.COORDINATOR)
        self.principal = StaffPrincipal(
            user_id=coordinator.id, organization_id=self.org.id, role=coordinator.role
        )
        self.coordinator_headers = staff_headers(settings, coordinator)
        viewer = build.user(self.org, Role.DEMO_VIEWER)
        self.viewer_headers = staff_headers(settings, viewer)
        self.now = dt.datetime.now(dt.UTC)

    def add_patient(self, *, first_name: str, mrn: str | None, phone: str | None) -> Patient:
        data = PatientCreate(
            first_name=first_name,
            last_name="Existing",
            date_of_birth=dt.date(1970, 1, 1),
            phone=phone,
            mrn=mrn,
            consent_to_message=True,
        )
        return PatientService(self.session).create(self.principal, data, now=self.now)

    def patient_count(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Patient)
                .where(Patient.organization_id == self.org.id)
            )
            or 0
        )


def hospital(build: Builder, db_session: Session, settings: Settings) -> Hospital:
    return Hospital(build, db_session, settings)


def request_body(
    csv_text: str, *, dry_run: bool = True, mapping: dict[str, str] | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"csv": csv_text, "dry_run": dry_run}
    if mapping is not None:
        body["mapping"] = mapping
    return body


def test_a_dry_run_reports_every_bad_row_and_writes_nothing(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            PATIENT_HEADER,
            "Asha,Patel,1968-03-14,+919812300001,asha@example.com,yes",
            "Ravi,Kumar,1971-07-02,+919812300002,bogus-marker@,no",
            ",Rao,1980-01-01,,,no",
            "Meena,Iyer,1990-05-05,12345,,no",
        ]
    )

    response = client.post(
        "/imports/patients", json=request_body(csv_text), headers=clinic.coordinator_headers
    )

    assert response.status_code == 200
    report = response.json()
    assert report["committed"] is False
    assert report["imported"] == 0
    assert report["rows"] == 4
    assert report["valid_rows"] == 1
    assert [error["line"] for error in report["errors"]] == [3, 4, 5]
    assert report["errors"][0]["column"] == "email"
    # The report names the problem but never repeats the value that caused it.
    assert "bogus-marker" not in response.text
    assert clinic.patient_count() == 0


def test_a_clean_file_commits_every_row_and_is_audited(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            PATIENT_HEADER,
            "Asha,Patel,1968-03-14,+919812300001,,yes",
            "Ravi,Kumar,1971-07-02,+919812300002,,no",
        ]
    )

    response = client.post(
        "/imports/patients",
        json=request_body(csv_text, dry_run=False),
        headers=clinic.coordinator_headers,
    )

    assert response.status_code == 200
    assert response.json()["committed"] is True
    assert response.json()["imported"] == 2
    assert clinic.patient_count() == 2
    summary = db_session.scalars(
        select(AuditLog).where(AuditLog.purpose == "bulk_import", AuditLog.entity_type == "import")
    ).all()
    assert [row.details for row in summary] == [{"count": 2}]


def test_one_bad_row_stops_the_whole_commit(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            PATIENT_HEADER,
            "Asha,Patel,1968-03-14,+919812300001,,yes",
            ",Nobody,1980-01-01,,,no",
        ]
    )

    response = client.post(
        "/imports/patients",
        json=request_body(csv_text, dry_run=False),
        headers=clinic.coordinator_headers,
    )

    assert response.json()["committed"] is False
    assert response.json()["imported"] == 0
    assert clinic.patient_count() == 0


def test_a_mrn_repeated_inside_the_file_is_caught_before_anything_is_saved(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            "first_name,last_name,date_of_birth,mrn",
            "Asha,Patel,1968-03-14,MRN-7",
            "Ravi,Kumar,1971-07-02,MRN-7",
        ]
    )

    report = client.post(
        "/imports/patients", json=request_body(csv_text), headers=clinic.coordinator_headers
    ).json()

    assert [error["line"] for error in report["errors"]] == [3]
    assert "already exists" in report["errors"][0]["message"]
    assert clinic.patient_count() == 0


def test_yes_and_no_columns_and_channel_words_are_read_plainly(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            "first_name,last_name,date_of_birth,consent_to_message,on_anticoagulant,"
            "preferred_channel",
            "Asha,Patel,1968-03-14,Y,yes,sms",
            "Ravi,Kumar,1971-07-02,maybe,no,sms",
        ]
    )

    report = client.post(
        "/imports/patients", json=request_body(csv_text), headers=clinic.coordinator_headers
    ).json()

    assert [error["line"] for error in report["errors"]] == [3]
    assert report["errors"][0]["column"] == "consent_to_message"
    assert report["errors"][0]["message"] == "is not yes or no"


def test_columns_can_be_mapped_and_unknown_ones_are_listed(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    csv_text = "\n".join(
        [
            "Given Name,Family,DOB,Clinic Notes",
            "Asha,Patel,1968-03-14,prefers mornings",
        ]
    )

    report = client.post(
        "/imports/patients",
        json=request_body(
            csv_text,
            mapping={"Given Name": "first_name", "Family": "last_name", "DOB": "date_of_birth"},
        ),
        headers=clinic.coordinator_headers,
    ).json()

    assert report["errors"] == []
    assert report["valid_rows"] == 1
    assert report["ignored_columns"] == ["Clinic Notes"]


def test_a_file_without_a_required_column_is_refused(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)

    response = client.post(
        "/imports/patients",
        json=request_body("first_name,date_of_birth\nAsha,1968-03-14"),
        headers=clinic.coordinator_headers,
    )

    assert response.status_code == 422
    assert "last_name" in response.text


def test_a_file_with_too_many_rows_is_refused(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    rows = [f"Patient{index},Test,1970-01-01" for index in range(501)]
    csv_text = "\n".join(["first_name,last_name,date_of_birth", *rows])

    response = client.post(
        "/imports/patients", json=request_body(csv_text), headers=clinic.coordinator_headers
    )

    assert response.status_code == 422
    assert "500 rows" in response.text


def test_appointments_find_the_patient_facility_and_procedure_by_name(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    existing = clinic.add_patient(first_name="Asha", mrn="MRN-100", phone="+919812300100")
    scheduled = (clinic.now + dt.timedelta(days=3)).astimezone(KOLKATA).isoformat()
    csv_text = "\n".join(
        [
            "patient_mrn,facility,procedure_code,scheduled_at",
            f"MRN-100,main campus,colonoscopy,{scheduled}",
        ]
    )

    report = client.post(
        "/imports/appointments",
        json=request_body(csv_text, dry_run=False),
        headers=clinic.coordinator_headers,
    ).json()

    assert report["committed"] is True
    appointment = db_session.scalar(
        select(Appointment).where(Appointment.patient_id == existing.id)
    )
    assert appointment is not None
    assert appointment.status is AppointmentStatus.SCHEDULED
    assert appointment.facility_id == clinic.facility.id


def test_appointment_rows_say_what_is_wrong_with_them(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    clinic.add_patient(first_name="Asha", mrn="MRN-100", phone="+919812300100")
    future = (clinic.now + dt.timedelta(days=3)).astimezone(KOLKATA).isoformat()
    csv_text = "\n".join(
        [
            "patient_mrn,patient_phone,facility,procedure_code,scheduled_at",
            f"MRN-100,,main campus,colonoscopy,{future}",
            f",,main campus,colonoscopy,{future}",
            f"MRN-999,,main campus,colonoscopy,{future}",
            f"MRN-100,,Nowhere,colonoscopy,{future}",
            "MRN-100,,main campus,colonoscopy,2001-01-01T09:00:00+05:30",
            f"MRN-100,,main campus,nosuchprocedure,{future}",
        ]
    )

    report = client.post(
        "/imports/appointments",
        json=request_body(csv_text),
        headers=clinic.coordinator_headers,
    ).json()

    messages = {error["line"]: error["message"] for error in report["errors"]}
    assert report["valid_rows"] == 1
    assert messages[3] == "needs patient_mrn or patient_phone"
    assert messages[4] == "No patient matches this MRN or phone"
    assert messages[5] == "No facility has this name"
    assert messages[6] == "The procedure must be scheduled in the future"
    assert messages[7] == "No procedure has this code"


def test_a_committed_appointment_import_reads_the_patient_under_audit(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)
    existing = clinic.add_patient(first_name="Asha", mrn=None, phone="+919812300100")
    scheduled = (clinic.now + dt.timedelta(days=3)).astimezone(KOLKATA).isoformat()
    csv_text = "\n".join(
        [
            "patient_phone,facility,procedure_code,scheduled_at",
            f"+919812300100,main campus,COLONOSCOPY,{scheduled}",
        ]
    )

    report = client.post(
        "/imports/appointments",
        json=request_body(csv_text, dry_run=False),
        headers=clinic.coordinator_headers,
    ).json()

    assert report["committed"] is True
    reads = db_session.scalars(
        select(AuditLog).where(
            AuditLog.purpose == "bulk_import",
            AuditLog.action == "READ",
            AuditLog.patient_id == existing.id,
        )
    ).all()
    assert reads


def test_viewers_cannot_import_either_kind(
    client: TestClient, build: Builder, db_session: Session, settings: Settings
) -> None:
    clinic = hospital(build, db_session, settings)

    patients = client.post(
        "/imports/patients",
        json=request_body(f"{PATIENT_HEADER}\n"),
        headers=clinic.viewer_headers,
    )
    appointments = client.post(
        "/imports/appointments",
        json=request_body("patient_mrn,facility,procedure_code,scheduled_at\n"),
        headers=clinic.viewer_headers,
    )

    assert patients.status_code == 403
    assert appointments.status_code == 403
