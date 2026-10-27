import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import Facility, Organization, ProcedureType


def get_organization(session: Session, organization_id: uuid.UUID) -> Organization | None:
    return session.get(Organization, organization_id)


def list_facilities(session: Session, organization_id: uuid.UUID) -> list[Facility]:
    return list(
        session.scalars(
            select(Facility)
            .where(Facility.organization_id == organization_id)
            .order_by(Facility.name)
        )
    )


def get_facility(
    session: Session, organization_id: uuid.UUID, facility_id: uuid.UUID
) -> Facility | None:
    return session.scalar(
        select(Facility).where(
            Facility.id == facility_id, Facility.organization_id == organization_id
        )
    )


def list_procedure_types(session: Session, organization_id: uuid.UUID) -> list[ProcedureType]:
    return list(
        session.scalars(
            select(ProcedureType)
            .where(ProcedureType.organization_id == organization_id)
            .order_by(ProcedureType.name)
        )
    )


def get_procedure_type(
    session: Session, organization_id: uuid.UUID, procedure_type_id: uuid.UUID
) -> ProcedureType | None:
    return session.scalar(
        select(ProcedureType).where(
            ProcedureType.id == procedure_type_id, ProcedureType.organization_id == organization_id
        )
    )


def get_procedure_type_by_code(
    session: Session, organization_id: uuid.UUID, code: str
) -> ProcedureType | None:
    return session.scalar(
        select(ProcedureType).where(
            ProcedureType.organization_id == organization_id, ProcedureType.code == code
        )
    )
