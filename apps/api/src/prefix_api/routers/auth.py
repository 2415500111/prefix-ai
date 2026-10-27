from fastapi import APIRouter, status

from prefix_api.api.deps import DbSession, Now, SettingsDep, StaffUser
from prefix_api.db.models import User
from prefix_api.domain.errors import AuthenticationError
from prefix_api.schemas.auth import LoginRequest, MeOut, RefreshRequest, TokenPairOut
from prefix_api.services.auth import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(pair: TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access_token=pair.access_token,
        access_expires_at=pair.access_expires_at,
        refresh_token=pair.refresh_token,
        refresh_expires_at=pair.refresh_expires_at,
    )


@router.post("/login")
def login(body: LoginRequest, session: DbSession, settings: SettingsDep, now: Now) -> TokenPairOut:
    return _out(AuthService(session, settings).login(body.email, body.password, now=now))


@router.post("/refresh")
def refresh(
    body: RefreshRequest, session: DbSession, settings: SettingsDep, now: Now
) -> TokenPairOut:
    return _out(AuthService(session, settings).refresh(body.refresh_token, now=now))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, session: DbSession, settings: SettingsDep, now: Now) -> None:
    AuthService(session, settings).logout(body.refresh_token, now=now)


@router.get("/me")
def me(principal: StaffUser, session: DbSession) -> MeOut:
    user = session.get(User, principal.user_id)
    if user is None:
        raise AuthenticationError("Account not found")
    return MeOut(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )
