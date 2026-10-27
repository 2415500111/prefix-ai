import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from prefix_api.api.deps import DbSession, Now, SettingsDep, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.protocols import ApproveIn, ProtocolIn, ProtocolOut, ProtocolSummaryOut
from prefix_api.services.embeddings import get_embedding_provider
from prefix_api.services.protocols import ProtocolService

router = APIRouter(prefix="/protocols", tags=["protocols"])

Reader = Annotated[StaffPrincipal, Depends(require(Permission.PROTOCOL_READ))]
Editor = Annotated[StaffPrincipal, Depends(require(Permission.PROTOCOL_EDIT))]
Approver = Annotated[StaffPrincipal, Depends(require(Permission.PROTOCOL_APPROVE))]


def _service(session: DbSession, settings: SettingsDep) -> ProtocolService:
    return ProtocolService(session, get_embedding_provider(settings.embedding_provider))


Service = Annotated[ProtocolService, Depends(_service)]


@router.get("")
def list_protocols(principal: Reader, service: Service) -> list[ProtocolSummaryOut]:
    return [ProtocolSummaryOut.model_validate(p) for p in service.list_latest(principal)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_protocol(body: ProtocolIn, principal: Editor, service: Service) -> ProtocolOut:
    return ProtocolOut.model_validate(service.create(principal, body))


@router.get("/{protocol_id}")
def get_protocol(protocol_id: uuid.UUID, principal: Reader, service: Service) -> ProtocolOut:
    return ProtocolOut.model_validate(service.get(principal, protocol_id))


@router.get("/{protocol_id}/versions")
def list_versions(
    protocol_id: uuid.UUID, principal: Reader, service: Service
) -> list[ProtocolSummaryOut]:
    return [ProtocolSummaryOut.model_validate(p) for p in service.versions(principal, protocol_id)]


@router.put("/{protocol_id}")
def edit_protocol(
    protocol_id: uuid.UUID, body: ProtocolIn, principal: Editor, service: Service
) -> ProtocolOut:
    """Edit a draft. For an approved or retired version this creates and returns a new draft."""
    return ProtocolOut.model_validate(service.edit(principal, protocol_id, body))


@router.post("/{protocol_id}/approve")
def approve_protocol(
    protocol_id: uuid.UUID, body: ApproveIn, principal: Approver, service: Service, now: Now
) -> ProtocolOut:
    protocol = service.approve(
        principal, protocol_id, acknowledge_sample=body.acknowledge_sample, now=now
    )
    return ProtocolOut.model_validate(protocol)
