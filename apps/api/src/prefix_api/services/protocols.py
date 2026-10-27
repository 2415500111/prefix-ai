"""Protocol Engine: versioned, clinician-approved prep protocols (safety rule a).

Rules enforced here and backed by database triggers (migration 0003):
- Only DRAFT versions can be changed. Editing an APPROVED or RETIRED version creates a new
  DRAFT version in the same family; a family has at most one draft at a time.
- Only roles with PROTOCOL_APPROVE (clinicians and admins) can approve. Approving retires the
  family's previously approved version.
- Only APPROVED versions can ever produce steps for a patient.
"""

import datetime as dt
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from prefix_api.db.models import PrepProtocol, PrepStep
from prefix_api.domain.conditions import PatientFacts, evaluate
from prefix_api.domain.enums import AuditAction, ProtocolStatus
from prefix_api.domain.errors import ConflictError, NotFoundError, ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import organizations as org_repo
from prefix_api.repositories import protocols as protocols_repo
from prefix_api.schemas.protocols import ProtocolIn, StepIn
from prefix_api.services.audit import record_audit
from prefix_api.services.embeddings import EmbeddingProvider

ENTITY = "prep_protocol"


class UnapprovedProtocolError(Exception):
    """Raised when code tries to use a protocol that is not APPROVED for a patient.

    This is a programming error, never a user error, so it is not a DomainError.
    """


@dataclass(frozen=True, slots=True)
class ApplicableStep:
    step: PrepStep
    protocol: PrepProtocol


def applicable_steps(protocol: PrepProtocol, facts: PatientFacts) -> list[PrepStep]:
    """Steps of an APPROVED protocol whose conditions match the patient."""
    if protocol.status is not ProtocolStatus.APPROVED:
        raise UnapprovedProtocolError(f"Protocol {protocol.id} is {protocol.status}")
    return [step for step in protocol.steps if evaluate(step.conditions, facts)]


def _step_rows(organization_id: uuid.UUID, steps: Sequence[StepIn]) -> list[PrepStep]:
    return [
        PrepStep(
            organization_id=organization_id,
            sort_order=index,
            offset_minutes=step.offset_minutes,
            title=step.title,
            instruction_text=step.instruction_text,
            category=step.category,
            requires_confirmation=step.requires_confirmation,
            is_critical=step.is_critical,
            conditions=step.conditions,
        )
        for index, step in enumerate(steps)
    ]


class ProtocolService:
    def __init__(self, session: Session, embedder: EmbeddingProvider) -> None:
        self._session = session
        self._embedder = embedder

    def list_latest(self, principal: StaffPrincipal) -> list[PrepProtocol]:
        principal.require(Permission.PROTOCOL_READ)
        return protocols_repo.list_latest_versions(self._session, principal.organization_id)

    def get(self, principal: StaffPrincipal, protocol_id: uuid.UUID) -> PrepProtocol:
        principal.require(Permission.PROTOCOL_READ)
        return self._load(principal, protocol_id)

    def versions(self, principal: StaffPrincipal, protocol_id: uuid.UUID) -> list[PrepProtocol]:
        principal.require(Permission.PROTOCOL_READ)
        protocol = self._load(principal, protocol_id)
        return protocols_repo.list_family(
            self._session, principal.organization_id, protocol.family_id
        )

    def create(
        self, principal: StaffPrincipal, data: ProtocolIn, *, is_sample: bool = False
    ) -> PrepProtocol:
        principal.require(Permission.PROTOCOL_EDIT)
        self._require_procedure_type(principal, data.procedure_type_id)
        protocol = PrepProtocol(
            organization_id=principal.organization_id,
            family_id=uuid.uuid7(),
            version=1,
            procedure_type_id=data.procedure_type_id,
            name=data.name,
            description=data.description,
            status=ProtocolStatus.DRAFT,
            is_sample=is_sample,
            created_by_id=principal.user_id,
            steps=_step_rows(principal.organization_id, data.steps),
        )
        self._session.add(protocol)
        self._session.flush()
        self._audit(principal, AuditAction.CREATE, protocol)
        return protocol

    def edit(
        self, principal: StaffPrincipal, protocol_id: uuid.UUID, data: ProtocolIn
    ) -> PrepProtocol:
        """Change a draft in place, or start a new draft from an approved/retired version."""
        principal.require(Permission.PROTOCOL_EDIT)
        protocol = self._load(principal, protocol_id, for_update=True)
        self._require_procedure_type(principal, data.procedure_type_id)

        if protocol.status is not ProtocolStatus.DRAFT:
            protocol = self._new_draft_from(principal, protocol)

        protocol.name = data.name
        protocol.description = data.description
        protocol.procedure_type_id = data.procedure_type_id
        protocol.steps.clear()
        self._session.flush()
        protocol.steps.extend(_step_rows(principal.organization_id, data.steps))
        self._session.flush()
        self._audit(principal, AuditAction.UPDATE, protocol)
        return protocol

    def approve(
        self,
        principal: StaffPrincipal,
        protocol_id: uuid.UUID,
        *,
        acknowledge_sample: bool,
        now: dt.datetime,
    ) -> PrepProtocol:
        principal.require(Permission.PROTOCOL_APPROVE)
        protocol = self._load(principal, protocol_id, for_update=True)
        if protocol.status is not ProtocolStatus.DRAFT:
            raise ConflictError(f"Only drafts can be approved (this version is {protocol.status})")
        if not protocol.steps:
            raise ValidationFailedError("A protocol needs at least one step before approval")
        if protocol.is_sample and not acknowledge_sample:
            raise ValidationFailedError(
                "This is a SAMPLE protocol. Confirm your clinical team has reviewed and "
                "adapted every step (acknowledge_sample) before approving it."
            )

        # Embed while still a draft: approved steps are immutable at the database level.
        vectors = self._embedder.embed([self._embedding_text(s) for s in protocol.steps])
        for step, vector in zip(protocol.steps, vectors, strict=True):
            step.embedding = vector
            step.embedding_model = self._embedder.name
        self._session.flush()

        for other in protocols_repo.list_family(
            self._session, principal.organization_id, protocol.family_id
        ):
            if other.status is ProtocolStatus.APPROVED:
                other.status = ProtocolStatus.RETIRED
        protocol.status = ProtocolStatus.APPROVED
        protocol.approved_by_id = principal.user_id
        protocol.approved_at = now
        self._session.flush()
        self._audit(principal, AuditAction.UPDATE, protocol, status="APPROVED")
        return protocol

    def _new_draft_from(self, principal: StaffPrincipal, source: PrepProtocol) -> PrepProtocol:
        family = protocols_repo.list_family(
            self._session, principal.organization_id, source.family_id
        )
        existing_draft = next((p for p in family if p.status is ProtocolStatus.DRAFT), None)
        if existing_draft is not None:
            raise ConflictError(
                f"Version {existing_draft.version} of this protocol is already a draft; edit it"
            )
        draft = PrepProtocol(
            organization_id=principal.organization_id,
            family_id=source.family_id,
            version=max(p.version for p in family) + 1,
            procedure_type_id=source.procedure_type_id,
            name=source.name,
            description=source.description,
            status=ProtocolStatus.DRAFT,
            is_sample=source.is_sample,
            created_by_id=principal.user_id,
        )
        self._session.add(draft)
        self._session.flush()
        return draft

    def _load(
        self, principal: StaffPrincipal, protocol_id: uuid.UUID, *, for_update: bool = False
    ) -> PrepProtocol:
        protocol = protocols_repo.get_protocol(
            self._session, principal.organization_id, protocol_id, for_update=for_update
        )
        if protocol is None:
            raise NotFoundError("Protocol not found")
        return protocol

    def _require_procedure_type(
        self, principal: StaffPrincipal, procedure_type_id: uuid.UUID
    ) -> None:
        if (
            org_repo.get_procedure_type(self._session, principal.organization_id, procedure_type_id)
            is None
        ):
            raise ValidationFailedError("Unknown procedure type")

    @staticmethod
    def _embedding_text(step: PrepStep) -> str:
        return f"{step.category.value}: {step.title}. {step.instruction_text}"

    def _audit(
        self,
        principal: StaffPrincipal,
        action: AuditAction,
        protocol: PrepProtocol,
        *,
        status: str | None = None,
    ) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=action,
            entity_type=ENTITY,
            entity_id=protocol.id,
            purpose="protocol_management",
            details={
                "family_id": str(protocol.family_id),
                **({"status": status} if status else {}),
            },
        )
