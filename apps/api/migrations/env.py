from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection, engine_from_config, pool
from sqlalchemy.types import TypeDecorator

import prefix_api.db.models  # noqa: F401  (registers all tables on Base.metadata)
from prefix_api.core.config import get_settings
from prefix_api.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    return url or get_settings().database_url.unicode_string()


def _render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    """Render app-level column types (e.g. encrypted text) as their plain DB type."""
    if type_ == "type" and isinstance(obj, TypeDecorator):
        return f"sa.{obj.impl_instance!r}"
    return False


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass an open connection so migrations run inside their transaction setup.
    connection: Connection | None = config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        return
    connectable = engine_from_config(
        {"sqlalchemy.url": _database_url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as conn:
        _configure(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
