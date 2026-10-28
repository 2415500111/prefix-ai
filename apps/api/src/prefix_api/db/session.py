from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings

type SessionFactory = sessionmaker[Session]

# Seconds to wait for the database before failing a request. Without it, an unreachable
# database holds the request for minutes.
DB_CONNECT_TIMEOUT_SECONDS = 5


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.unicode_string(),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        connect_args={"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS},
    )


def database_location(engine: Engine) -> str:
    """The host and port for log messages, e.g. 127.0.0.1:55432. Never includes credentials."""
    url = engine.url
    return f"{url.host}:{url.port or 5432}"


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, expire_on_commit=False)
