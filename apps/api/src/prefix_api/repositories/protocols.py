import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from prefix_api.db.models import PrepProtocol
from prefix_api.domain.enums import ProtocolStatus


def get_protocol(
    session: Session,
    organization_id: uuid.UUID,
    protocol_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> PrepProtocol | None:
    query = (
        select(PrepProtocol)
        .where(PrepProtocol.id == protocol_id, PrepProtocol.organization_id == organization_id)
        .options(selectinload(PrepProtocol.steps))
    )
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def list_latest_versions(session: Session, organization_id: uuid.UUID) -> list[PrepProtocol]:
    """The newest version of every protocol family in the organization."""
    latest = (
        select(PrepProtocol.family_id, func.max(PrepProtocol.version).label("version"))
        .where(PrepProtocol.organization_id == organization_id)
        .group_by(PrepProtocol.family_id)
        .subquery()
    )
    query = (
        select(PrepProtocol)
        .join(
            latest,
            (PrepProtocol.family_id == latest.c.family_id)
            & (PrepProtocol.version == latest.c.version),
        )
        .where(PrepProtocol.organization_id == organization_id)
        .order_by(PrepProtocol.name)
    )
    return list(session.scalars(query))


def list_family(
    session: Session, organization_id: uuid.UUID, family_id: uuid.UUID
) -> list[PrepProtocol]:
    return list(
        session.scalars(
            select(PrepProtocol)
            .where(
                PrepProtocol.organization_id == organization_id,
                PrepProtocol.family_id == family_id,
            )
            .order_by(PrepProtocol.version)
            .with_for_update()
        )
    )


def list_approved_for_procedure(
    session: Session, organization_id: uuid.UUID, procedure_type_id: uuid.UUID
) -> list[PrepProtocol]:
    return list(
        session.scalars(
            select(PrepProtocol)
            .where(
                PrepProtocol.organization_id == organization_id,
                PrepProtocol.procedure_type_id == procedure_type_id,
                PrepProtocol.status == ProtocolStatus.APPROVED,
            )
            .options(selectinload(PrepProtocol.steps))
            .order_by(PrepProtocol.name)
        )
    )
