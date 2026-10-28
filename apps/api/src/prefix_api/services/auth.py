"""Staff authentication: password login, rotating refresh tokens, logout."""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.core.crypto import normalize_email
from prefix_api.core.security import (
    hash_opaque_token,
    hash_password,
    issue_access_token,
    new_opaque_token,
    password_needs_rehash,
    verify_password,
)
from prefix_api.db.models import RefreshToken, User
from prefix_api.domain.enums import AuditAction
from prefix_api.domain.errors import AuthenticationError
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import users as users_repo
from prefix_api.services.audit import record_audit

_INVALID_CREDENTIALS = "Invalid email or password"
_INVALID_REFRESH = "Invalid or expired refresh token"


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    access_expires_at: dt.datetime
    refresh_token: str
    refresh_expires_at: dt.datetime


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def login(self, email: str, password: str, *, now: dt.datetime) -> TokenPair:
        user = users_repo.get_user_by_email(self._session, normalize_email(email))
        valid = verify_password(password, user.password_hash if user else None)
        if user is None or not valid or not user.is_active:
            if user is not None:
                record_audit(
                    self._session,
                    principal=None,
                    organization_id=user.organization_id,
                    action=AuditAction.LOGIN_FAILED,
                    entity_type="user",
                    entity_id=user.id,
                    purpose="authentication",
                    details={"reason": "inactive" if valid else "bad_password"},
                )
                # Persist the audit row even though the request fails.
                self._session.commit()
            raise AuthenticationError(_INVALID_CREDENTIALS)

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = now
        record_audit(
            self._session,
            principal=self._principal(user),
            action=AuditAction.LOGIN,
            entity_type="user",
            entity_id=user.id,
            purpose="authentication",
        )
        return self._issue_pair(user, family_id=uuid.uuid7(), now=now)

    def refresh(self, refresh_token: str, *, now: dt.datetime) -> TokenPair:
        stored = users_repo.get_refresh_token_for_update(
            self._session, hash_opaque_token(refresh_token)
        )
        if stored is None or stored.expires_at <= now:
            raise AuthenticationError(_INVALID_REFRESH)

        user = self._session.get(User, stored.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError(_INVALID_REFRESH)

        if stored.revoked_at is not None:
            # A rotated token was presented again: it may have been stolen. Revoke every
            # token from this login so neither the thief nor the user can continue.
            users_repo.revoke_refresh_family(self._session, stored.family_id, now)
            record_audit(
                self._session,
                principal=self._principal(user),
                action=AuditAction.TOKEN_REUSE_DETECTED,
                entity_type="user",
                entity_id=user.id,
                purpose="authentication",
            )
            # The revocation must survive the error response below.
            self._session.commit()
            raise AuthenticationError(_INVALID_REFRESH)

        stored.revoked_at = now
        record_audit(
            self._session,
            principal=self._principal(user),
            action=AuditAction.TOKEN_REFRESH,
            entity_type="user",
            entity_id=user.id,
            purpose="authentication",
        )
        return self._issue_pair(user, family_id=stored.family_id, now=now)

    def logout(self, refresh_token: str, *, now: dt.datetime) -> None:
        stored = users_repo.get_refresh_token_for_update(
            self._session, hash_opaque_token(refresh_token)
        )
        if stored is None:
            return
        users_repo.revoke_refresh_family(self._session, stored.family_id, now)
        user = self._session.get(User, stored.user_id)
        if user is not None:
            record_audit(
                self._session,
                principal=self._principal(user),
                action=AuditAction.LOGOUT,
                entity_type="user",
                entity_id=user.id,
                purpose="authentication",
            )

    def guest_session(self, user: User, *, now: dt.datetime) -> TokenPair:
        """A short demo session for a guest user (no password). It ends after
        ``guest_session_minutes``; the refresh token cannot outlive it."""
        record_audit(
            self._session,
            principal=self._principal(user),
            action=AuditAction.LOGIN,
            entity_type="user",
            entity_id=user.id,
            purpose="guest_login",
        )
        return self._issue_pair(
            user,
            family_id=uuid.uuid7(),
            now=now,
            refresh_ttl=dt.timedelta(minutes=self._settings.guest_session_minutes),
        )

    def _issue_pair(
        self,
        user: User,
        *,
        family_id: uuid.UUID,
        now: dt.datetime,
        refresh_ttl: dt.timedelta | None = None,
    ) -> TokenPair:
        access_token, access_expires_at = issue_access_token(
            self._settings,
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role,
            now=now,
        )
        refresh_token = new_opaque_token()
        ttl = refresh_ttl or dt.timedelta(days=self._settings.jwt_refresh_ttl_days)
        refresh_expires_at = now + ttl
        users_repo.add_refresh_token(
            self._session,
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_opaque_token(refresh_token),
                issued_at=now,
                expires_at=refresh_expires_at,
            ),
        )
        return TokenPair(access_token, access_expires_at, refresh_token, refresh_expires_at)

    @staticmethod
    def _principal(user: User) -> StaffPrincipal:
        return StaffPrincipal(user_id=user.id, organization_id=user.organization_id, role=user.role)
