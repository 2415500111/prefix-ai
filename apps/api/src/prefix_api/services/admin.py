"""Organization administration: staff users, facilities and procedure types."""

from sqlalchemy.orm import Session

from prefix_api.core.crypto import normalize_email
from prefix_api.core.security import hash_password
from prefix_api.db.models import Facility, ProcedureType, User
from prefix_api.domain.enums import AuditAction
from prefix_api.domain.errors import ConflictError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import organizations as org_repo
from prefix_api.repositories import users as users_repo
from prefix_api.schemas.admin import FacilityCreate, ProcedureTypeCreate, UserCreate
from prefix_api.services._db import flush_or_conflict
from prefix_api.services.audit import record_audit


class AdminService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(self, principal: StaffPrincipal, data: UserCreate) -> User:
        principal.require(Permission.USER_MANAGE)
        email = normalize_email(data.email)
        if users_repo.get_user_by_email(self._session, email) is not None:
            raise ConflictError("A user with this email already exists")
        user = User(
            organization_id=principal.organization_id,
            email=email,
            full_name=data.full_name,
            role=data.role,
            password_hash=hash_password(data.password),
        )
        self._session.add(user)
        self._session.flush()
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="user",
            entity_id=user.id,
            purpose="user_administration",
            details={"target_role": data.role.value},
        )
        return user

    def list_users(self, principal: StaffPrincipal) -> list[User]:
        principal.require(Permission.USER_MANAGE)
        return users_repo.list_users(self._session, principal.organization_id)

    def create_facility(self, principal: StaffPrincipal, data: FacilityCreate) -> Facility:
        principal.require(Permission.FACILITY_MANAGE)
        facility = Facility(
            organization_id=principal.organization_id,
            name=data.name,
            timezone=data.timezone,
            address=data.address,
            maps_url=str(data.maps_url) if data.maps_url else None,
            phone=data.phone,
        )
        flush_or_conflict(self._session, "A facility with this name already exists", facility)
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="facility",
            entity_id=facility.id,
            purpose="facility_administration",
        )
        return facility

    def list_facilities(self, principal: StaffPrincipal) -> list[Facility]:
        return org_repo.list_facilities(self._session, principal.organization_id)

    def create_procedure_type(
        self, principal: StaffPrincipal, data: ProcedureTypeCreate
    ) -> ProcedureType:
        principal.require(Permission.FACILITY_MANAGE)
        procedure_type = ProcedureType(
            organization_id=principal.organization_id, **data.model_dump()
        )
        flush_or_conflict(
            self._session, "A procedure type with this code already exists", procedure_type
        )
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="procedure_type",
            entity_id=procedure_type.id,
            purpose="facility_administration",
        )
        return procedure_type

    def list_procedure_types(self, principal: StaffPrincipal) -> list[ProcedureType]:
        return org_repo.list_procedure_types(self._session, principal.organization_id)
