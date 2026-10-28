import hashlib

from fastapi import APIRouter, Request, status

from prefix_api.api.deps import DbSession, Now, SettingsDep, StaffUser
from prefix_api.core.crypto import normalize_email
from prefix_api.core.rate_limit import RateLimiter
from prefix_api.db.models import User
from prefix_api.domain.errors import AuthenticationError, NotFoundError
from prefix_api.schemas.auth import LoginRequest, MeOut, RefreshRequest, TokenPairOut
from prefix_api.schemas.demo import CapabilitiesOut
from prefix_api.services.auth import AuthService, TokenPair
from prefix_api.services.demo import guest_login

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(pair: TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access_token=pair.access_token,
        access_expires_at=pair.access_expires_at,
        refresh_token=pair.refresh_token,
        refresh_expires_at=pair.refresh_expires_at,
    )


# Guests may try the demo this many times per client address in each window.
GUEST_LOGINS_PER_WINDOW = 5
GUEST_WINDOW_SECONDS = 600.0
# Password guessing is limited per account and per client address. Only failed attempts count,
# so ordinary sign-ins never use up the allowance. The account limit is the one that matters;
# the client limit is a backstop for one address trying many accounts.
LOGIN_PER_ACCOUNT = 10
LOGIN_PER_CLIENT = 100
LOGIN_WINDOW_SECONDS = 900.0


@router.get("/capabilities")
def capabilities(settings: SettingsDep) -> CapabilitiesOut:
    """What the sign-in page may offer. Clients should not guess at feature flags."""
    return CapabilitiesOut(guest_login=settings.enable_guest_login)


@router.post("/guest")
def guest(request: Request, session: DbSession, settings: SettingsDep, now: Now) -> TokenPairOut:
    """Sign in to the synthetic demo hospital as a guest. Off unless ENABLE_GUEST_LOGIN is set."""
    if not settings.enable_guest_login:
        raise NotFoundError("Not found")
    limiter: RateLimiter = request.app.state.rate_limiter
    client = request.client.host if request.client else "unknown"
    limiter.check(
        f"guest-login:{client}",
        limit=GUEST_LOGINS_PER_WINDOW,
        window_seconds=GUEST_WINDOW_SECONDS,
    )
    return _out(guest_login(session, settings, now=now))


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    session: DbSession,
    settings: SettingsDep,
    now: Now,
) -> TokenPairOut:
    limiter: RateLimiter = request.app.state.rate_limiter
    client_key = f"login-client:{request.client.host if request.client else 'unknown'}"
    # Keyed by a hash so the limiter never holds an address in plain text.
    account_key = (
        f"login-account:{hashlib.sha256(normalize_email(body.email).encode()).hexdigest()}"
    )
    limiter.refuse_if_full(client_key, limit=LOGIN_PER_CLIENT, window_seconds=LOGIN_WINDOW_SECONDS)
    limiter.refuse_if_full(
        account_key, limit=LOGIN_PER_ACCOUNT, window_seconds=LOGIN_WINDOW_SECONDS
    )
    try:
        pair = AuthService(session, settings).login(body.email, body.password, now=now)
    except AuthenticationError:
        limiter.record(client_key)
        limiter.record(account_key)
        raise
    return _out(pair)


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
