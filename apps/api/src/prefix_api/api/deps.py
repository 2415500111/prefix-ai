"""FastAPI dependencies: settings, DB session, authentication and RBAC."""

import datetime as dt
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.core.request_context import current_request_context
from prefix_api.core.security import InvalidTokenError, decode_token
from prefix_api.db.models import User
from prefix_api.domain.errors import AuthenticationError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import PatientPrincipal, StaffPrincipal
from prefix_api.services.assistant.llm import AssistantLLM

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    """One session per request: commit on success, roll back on any error."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_assistant_llm(request: Request) -> AssistantLLM | None:
    """Built once per app; None when no LLM is configured (questions go to nurses)."""
    llm: AssistantLLM | None = request.app.state.assistant_llm
    return llm


AssistantLLMDep = Annotated[AssistantLLM | None, Depends(get_assistant_llm)]
# scope="function": commit BEFORE the response is sent, so a failed commit (including
# its audit rows) can never be reported to the client as success.
DbSession = Annotated[Session, Depends(get_db, scope="function")]
Now = Annotated[dt.datetime, Depends(utcnow)]
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def get_staff_principal(
    credentials: BearerToken, settings: SettingsDep, session: DbSession
) -> StaffPrincipal:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    try:
        claims = decode_token(settings, credentials.credentials, "access")
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc

    # Check the account is still active and its role unchanged, so deactivation and role
    # changes take effect immediately rather than when the access token expires.
    user = session.get(User, claims.subject)
    if (
        user is None
        or not user.is_active
        or user.organization_id != claims.organization_id
        or user.role != claims.role
    ):
        raise AuthenticationError("Invalid or expired access token")
    return StaffPrincipal(user_id=user.id, organization_id=user.organization_id, role=user.role)


def get_patient_principal(credentials: BearerToken, settings: SettingsDep) -> PatientPrincipal:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    try:
        claims = decode_token(settings, credentials.credentials, "patient")
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired patient session") from exc
    return PatientPrincipal(patient_id=claims.subject, organization_id=claims.organization_id)


StaffUser = Annotated[StaffPrincipal, Depends(get_staff_principal)]
CurrentPatient = Annotated[PatientPrincipal, Depends(get_patient_principal)]


def require(permission: Permission) -> Callable[[StaffPrincipal], StaffPrincipal]:
    """RBAC dependency: rejects the request early if the role lacks ``permission``.

    Services check again (defense in depth); this gives a clean 403 before any work.
    """

    def dependency(principal: StaffUser) -> StaffPrincipal:
        principal.require(permission)
        return principal

    return dependency


def patient_data_route() -> None:
    """Marks a route as handling patient data, so the audit backstop checks it."""
    context = current_request_context()
    if context is not None:
        context.touches_patient_data = True
