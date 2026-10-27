from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings

type SessionFactory = sessionmaker[Session]


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.unicode_string(),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
    )


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, expire_on_commit=False)
