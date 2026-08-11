from collections.abc import Callable
from typing import Final, Protocol, cast

from sqlalchemy import event
from sqlalchemy.engine.interfaces import AdaptedConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from relationship_network_api.config import DatabaseSettings

APP_DATABASE_ROLE: Final = "relationship_app"
"""Non-superuser role application connections assume so row level security applies."""
PLATFORM_WORKER_DATABASE_ROLE: Final = "relationship_platform_worker"
OUTBOX_DISPATCHER_DATABASE_ROLE: Final = "relationship_outbox_dispatcher"
LLM_MAINTENANCE_DATABASE_ROLE: Final = "relationship_llm_maintenance"
REQUIREMENT_SCHEDULER_DATABASE_ROLE: Final = "relationship_requirement_scheduler"
_ALLOWED_DATABASE_ROLES: Final = frozenset(
    {
        APP_DATABASE_ROLE,
        PLATFORM_WORKER_DATABASE_ROLE,
        OUTBOX_DISPATCHER_DATABASE_ROLE,
        LLM_MAINTENANCE_DATABASE_ROLE,
        REQUIREMENT_SCHEDULER_DATABASE_ROLE,
    }
)


class _DbapiCursor(Protocol):
    def execute(self, operation: str) -> None: ...

    def close(self) -> None: ...


class _DbapiConnection(Protocol):
    def cursor(self) -> _DbapiCursor: ...


def _assume_app_role(dbapi_connection: AdaptedConnection, _record: object) -> None:
    _assume_role(dbapi_connection, APP_DATABASE_ROLE)


def _assume_role(dbapi_connection: AdaptedConnection, role: str) -> None:
    cursor = cast("_DbapiConnection", cast("object", dbapi_connection)).cursor()
    try:
        cursor.execute(f"SET ROLE {role}")
    finally:
        cursor.close()


def _role_listener(role: str) -> Callable[[AdaptedConnection, object], None]:
    if role not in _ALLOWED_DATABASE_ROLES:
        message = f"unsupported database role: {role}"
        raise ValueError(message)

    def listener(dbapi_connection: AdaptedConnection, _record: object) -> None:
        _assume_role(dbapi_connection, role)

    return listener


def create_engine_from_settings(
    settings: DatabaseSettings,
    *,
    database_role: str = APP_DATABASE_ROLE,
) -> AsyncEngine:
    """Build the async SQLAlchemy engine for the configured database.

    Every pooled connection assumes the non-superuser application role so
    PostgreSQL row level security is enforced for all application queries.
    """
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    _ = event.listens_for(engine.sync_engine, "connect")(_role_listener(database_role))
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory shared by request-scoped dependencies."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
