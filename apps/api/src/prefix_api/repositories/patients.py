import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from prefix_api.db.models import Patient, PatientMagicLink


def get_patient(
    session: Session, organization_id: uuid.UUID, patient_id: uuid.UUID
) -> Patient | None:
    return session.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.organization_id == organization_id)
    )


def search_patients(
    session: Session,
    organization_id: uuid.UUID,
    *,
    phone_bidx: str | None = None,
    email_bidx: str | None = None,
    mrn_bidx: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Patient]:
    query = select(Patient).where(Patient.organization_id == organization_id)
    if phone_bidx is not None:
        query = query.where(Patient.phone_bidx == phone_bidx)
    if email_bidx is not None:
        query = query.where(Patient.email_bidx == email_bidx)
    if mrn_bidx is not None:
        query = query.where(Patient.mrn_bidx == mrn_bidx)
    query = query.order_by(Patient.created_at.desc(), Patient.id).limit(limit).offset(offset)
    return list(session.scalars(query))


def add_magic_link(session: Session, link: PatientMagicLink) -> None:
    session.add(link)


def consume_magic_link(
    session: Session, token_hash: str, now: dt.datetime
) -> PatientMagicLink | None:
    """Atomically mark an unused, unexpired link as used. Returns None if not redeemable."""
    link_id = session.scalar(
        update(PatientMagicLink)
        .where(
            PatientMagicLink.token_hash == token_hash,
            PatientMagicLink.used_at.is_(None),
            PatientMagicLink.expires_at > now,
        )
        .values(used_at=now)
        .returning(PatientMagicLink.id)
    )
    if link_id is None:
        return None
    return session.get(PatientMagicLink, link_id)
