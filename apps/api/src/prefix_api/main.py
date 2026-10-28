from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from prefix_api import __version__
from prefix_api.api.errors import register_error_handlers
from prefix_api.core.config import Settings, get_settings
from prefix_api.core.crypto import configure_crypto
from prefix_api.core.logging import configure_logging, get_logger
from prefix_api.core.middleware import (
    REQUEST_ID_HEADER,
    audit_backstop_middleware,
    request_context_middleware,
)
from prefix_api.db.session import (
    SessionFactory,
    create_db_engine,
    create_session_factory,
    database_location,
)
from prefix_api.routers import (
    admin,
    appointments,
    auth,
    health,
    patient_portal,
    patients,
    protocols,
    webhooks,
)
from prefix_api.services.assistant.llm import build_assistant_llm

logger = get_logger(__name__)


def _log_database_reachability(session_factory: SessionFactory) -> None:
    """Report at startup whether the database answers. The API still starts so /health works;
    requests that need the database then fail fast with a 503 and the same log line."""
    engine = session_factory.kw["bind"]
    where = database_location(engine)
    try:
        with engine.connect():
            pass
    except OperationalError:
        logger.error(f"Database not reachable at {where}")
        return
    logger.info("database.reachable", where=where)


def create_app(
    settings: Settings | None = None, session_factory: SessionFactory | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    configure_crypto(settings)

    owns_engine = session_factory is None
    if session_factory is None:
        session_factory = create_session_factory(create_db_engine(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if owns_engine:
            _log_database_reachability(session_factory)
        yield
        if owns_engine and session_factory.kw.get("bind") is not None:
            session_factory.kw["bind"].dispose()

    app = FastAPI(
        title="Prefix AI API",
        version=__version__,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.assistant_llm = build_assistant_llm(settings)

    register_error_handlers(app)

    # Starlette runs the most recently added middleware first (outermost).
    app.middleware("http")(audit_backstop_middleware)
    app.middleware("http")(request_context_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(patients.router)
    app.include_router(patient_portal.router)
    app.include_router(protocols.router)
    app.include_router(appointments.router)
    app.include_router(webhooks.router)
    return app
