from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from api_testkit import TEST_DATABASE_URL, Builder, make_test_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.config import Settings
from prefix_api.core.crypto import configure_crypto
from prefix_api.main import create_app

type SettingsFactory = Callable[..., Settings]

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def make_settings() -> SettingsFactory:
    """Build Settings from explicit values only, ignoring the environment and `.env`."""
    return make_test_settings


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture(autouse=True, scope="session")
def _configure_test_crypto() -> None:
    configure_crypto(make_test_settings())


def _ensure_database_exists(url: str) -> None:
    parsed = make_url(url)
    admin_url = parsed.set(drivername="postgresql", database="postgres")
    conninfo = admin_url.render_as_string(hide_password=False)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (parsed.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{parsed.database}"')


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A freshly migrated test database. Running the real migrations tests them too."""
    _ensure_database_exists(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        config = Config(str(_ALEMBIC_INI))
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(engine: Engine) -> Iterator[Connection]:
    """One connection per test inside a transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_factory(db_connection: Connection) -> sessionmaker[Session]:
    # Sessions join the test transaction; their commits only release savepoints.
    return sessionmaker(
        bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def build(db_session: Session) -> Builder:
    return Builder(db_session)


@pytest.fixture
def app(settings: Settings, session_factory: sessionmaker[Session]) -> FastAPI:
    return create_app(settings, session_factory=session_factory)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
