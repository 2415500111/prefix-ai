import uuid
from dataclasses import dataclass

from prefix_api.domain.enums import ActorType, Role
from prefix_api.domain.errors import PermissionDeniedError
from prefix_api.domain.permissions import Permission, role_has


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: Role

    @property
    def actor_type(self) -> ActorType:
        return ActorType.USER

    @property
    def actor_id(self) -> uuid.UUID:
        return self.user_id

    def can(self, permission: Permission) -> bool:
        return role_has(self.role, permission)

    def require(self, permission: Permission) -> None:
        if not self.can(permission):
            raise PermissionDeniedError(f"Role {self.role} lacks {permission}")


@dataclass(frozen=True, slots=True)
class PatientPrincipal:
    patient_id: uuid.UUID
    organization_id: uuid.UUID

    @property
    def actor_type(self) -> ActorType:
        return ActorType.PATIENT

    @property
    def actor_id(self) -> uuid.UUID:
        return self.patient_id


@dataclass(frozen=True, slots=True)
class SystemPrincipal:
    """Background jobs (Celery tasks) acting on behalf of an organization."""

    organization_id: uuid.UUID
    job: str

    @property
    def actor_type(self) -> ActorType:
        return ActorType.SYSTEM

    @property
    def actor_id(self) -> None:
        return None


type Principal = StaffPrincipal | PatientPrincipal | SystemPrincipal
