import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from prefix_api.db.models import RefreshToken, User


def get_user_by_email(session: Session, email: str) -> User | None:
    """Global lookup: email addresses are unique across organizations (used for login)."""
    return session.scalar(select(User).where(User.email == email))


def get_user(session: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    return session.scalar(
        select(User).where(User.id == user_id, User.organization_id == organization_id)
    )


def list_users(session: Session, organization_id: uuid.UUID) -> list[User]:
    return list(
        session.scalars(
            select(User).where(User.organization_id == organization_id).order_by(User.full_name)
        )
    )


def add_refresh_token(session: Session, token: RefreshToken) -> None:
    session.add(token)


def get_refresh_token_for_update(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )


def revoke_refresh_family(session: Session, family_id: uuid.UUID, now: dt.datetime) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
