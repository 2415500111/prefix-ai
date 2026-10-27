"""Password hashing and token handling for staff and patients."""

import datetime as dt
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from prefix_api.core.config import Settings
from prefix_api.domain.enums import Role

type TokenType = Literal["access", "patient"]

_ALGORITHM = "HS256"
_password_hasher = PasswordHasher()
# Verified against when the email is unknown, so response time does not reveal which
# emails have accounts.
_DUMMY_HASH = _password_hasher.hash(secrets.token_urlsafe(16))


class InvalidTokenError(Exception):
    """The token is malformed, expired, of the wrong type or has a bad signature."""


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _password_hasher.verify(password_hash or _DUMMY_HASH, password) and (
            password_hash is not None
        )
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def new_opaque_token() -> str:
    """A random URL-safe secret for refresh tokens and magic links (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: uuid.UUID
    organization_id: uuid.UUID
    token_type: TokenType
    role: Role | None
    expires_at: dt.datetime


def _encode(
    *,
    settings: Settings,
    subject: uuid.UUID,
    organization_id: uuid.UUID,
    token_type: TokenType,
    ttl: dt.timedelta,
    now: dt.datetime,
    role: Role | None = None,
) -> tuple[str, dt.datetime]:
    expires_at = now + ttl
    payload: dict[str, object] = {
        "iss": settings.jwt_issuer,
        "sub": str(subject),
        "org": str(organization_id),
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if role is not None:
        payload["role"] = role.value
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITHM)
    return token, expires_at


def issue_access_token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: Role,
    now: dt.datetime,
) -> tuple[str, dt.datetime]:
    return _encode(
        settings=settings,
        subject=user_id,
        organization_id=organization_id,
        token_type="access",
        ttl=dt.timedelta(minutes=settings.jwt_access_ttl_minutes),
        now=now,
        role=role,
    )


def issue_patient_token(
    settings: Settings,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID,
    now: dt.datetime,
) -> tuple[str, dt.datetime]:
    return _encode(
        settings=settings,
        subject=patient_id,
        organization_id=organization_id,
        token_type="patient",
        ttl=dt.timedelta(minutes=settings.patient_session_ttl_minutes),
        now=now,
    )


def decode_token(settings: Settings, token: str, expected_type: TokenType) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[_ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "typ", "org"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("typ") != expected_type:
        raise InvalidTokenError("Wrong token type")
    try:
        role = Role(payload["role"]) if expected_type == "access" else None
        return TokenClaims(
            subject=uuid.UUID(payload["sub"]),
            organization_id=uuid.UUID(payload["org"]),
            token_type=expected_type,
            role=role,
            expires_at=dt.datetime.fromtimestamp(payload["exp"], tz=dt.UTC),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Malformed token claims") from exc
