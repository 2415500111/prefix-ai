import datetime as dt

from api_testkit import Builder
from sqlalchemy import text
from sqlalchemy.orm import Session

from prefix_api.db.models import Patient

ENCRYPTED_COLUMNS = ("first_name", "last_name", "date_of_birth", "phone", "email")


def test_patient_pii_is_stored_encrypted(build: Builder, db_session: Session) -> None:
    org = build.organization()
    patient = build.patient(
        org,
        first_name="Asha",
        last_name="Verma",
        date_of_birth=dt.date(1961, 4, 12),
        phone="+919876500001",
        email="asha@example.com",
    )

    row = db_session.execute(
        text(f"SELECT {', '.join(ENCRYPTED_COLUMNS)} FROM patient WHERE id = :id"),  # noqa: S608
        {"id": patient.id},
    ).one()

    raw = dict(zip(ENCRYPTED_COLUMNS, row, strict=True))
    for column, value in raw.items():
        assert value.startswith("enc:v1:"), column
    stored = " ".join(raw.values())
    for plaintext in ("Asha", "Verma", "1961-04-12", "9876500001", "asha@example"):
        assert plaintext not in stored


def test_patient_pii_decrypts_through_the_orm(build: Builder, db_session: Session) -> None:
    org = build.organization()
    patient = build.patient(org, first_name="Asha", date_of_birth=dt.date(1961, 4, 12))
    db_session.expire_all()

    loaded = db_session.get(Patient, patient.id)

    assert loaded is not None
    assert loaded.first_name == "Asha"
    assert loaded.date_of_birth == dt.date(1961, 4, 12)


def test_blind_indexes_are_not_plaintext(build: Builder, db_session: Session) -> None:
    org = build.organization()
    patient = build.patient(org, phone="+919876500002")

    phone_bidx = db_session.scalar(
        text("SELECT phone_bidx FROM patient WHERE id = :id"), {"id": patient.id}
    )

    assert phone_bidx is not None
    assert "9876500002" not in phone_bidx
    assert len(phone_bidx) == 64
