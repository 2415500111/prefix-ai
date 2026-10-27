from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prefix_api.db.base import Base
from prefix_api.domain.errors import ConflictError


def flush_or_conflict(session: Session, message: str, *new_objects: Base) -> None:
    """Flush inside a savepoint; turn a unique-constraint violation into a ConflictError.

    Rolling back only the savepoint keeps the rest of the request's transaction usable.
    """
    try:
        with session.begin_nested():
            session.add_all(new_objects)
            session.flush()
    except IntegrityError as exc:
        raise ConflictError(message) from exc
