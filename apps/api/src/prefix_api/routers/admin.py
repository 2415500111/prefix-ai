from typing import Annotated

from fastapi import APIRouter, Depends, status

from prefix_api.api.deps import DbSession, StaffUser, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.admin import (
    FacilityCreate,
    FacilityOut,
    ProcedureTypeCreate,
    ProcedureTypeOut,
    UserCreate,
    UserOut,
)
from prefix_api.services.admin import AdminService

router = APIRouter(tags=["admin"])

UserManager = Annotated[StaffPrincipal, Depends(require(Permission.USER_MANAGE))]
FacilityManager = Annotated[StaffPrincipal, Depends(require(Permission.FACILITY_MANAGE))]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, principal: UserManager, session: DbSession) -> UserOut:
    return UserOut.model_validate(AdminService(session).create_user(principal, body))


@router.get("/users")
def list_users(principal: UserManager, session: DbSession) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in AdminService(session).list_users(principal)]


@router.post("/facilities", status_code=status.HTTP_201_CREATED)
def create_facility(
    body: FacilityCreate, principal: FacilityManager, session: DbSession
) -> FacilityOut:
    return FacilityOut.model_validate(AdminService(session).create_facility(principal, body))


@router.get("/facilities")
def list_facilities(principal: StaffUser, session: DbSession) -> list[FacilityOut]:
    facilities = AdminService(session).list_facilities(principal)
    return [FacilityOut.model_validate(f) for f in facilities]


@router.post("/procedure-types", status_code=status.HTTP_201_CREATED)
def create_procedure_type(
    body: ProcedureTypeCreate, principal: FacilityManager, session: DbSession
) -> ProcedureTypeOut:
    created = AdminService(session).create_procedure_type(principal, body)
    return ProcedureTypeOut.model_validate(created)


@router.get("/procedure-types")
def list_procedure_types(principal: StaffUser, session: DbSession) -> list[ProcedureTypeOut]:
    types = AdminService(session).list_procedure_types(principal)
    return [ProcedureTypeOut.model_validate(t) for t in types]
