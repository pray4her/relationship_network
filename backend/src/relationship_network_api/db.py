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


class _DbapiCursor(Protocol):
    def execute(self, operation: str) -> None: ...

    def close(self) -> None: ...


class _DbapiConnection(Protocol):
    def cursor(self) -> _DbapiCursor: ...


def _assume_app_role(dbapi_connection: AdaptedConnection, _record: object) -> None:
    cursor = cast("_DbapiConnection", cast("object", dbapi_connection)).cursor()
    try:
        cursor.execute(f"SET ROLE {APP_DATABASE_ROLE}")
    finally:
        cursor.close()


def create_engine_from_settings(settings: DatabaseSettings) -> AsyncEngine:
    """Build the async SQLAlchemy engine for the configured database.

    Every pooled connection assumes the non-superuser application role so
    PostgreSQL row level security is enforced for all application queries.
    """
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    _ = event.listens_for(engine.sync_engine, "connect")(_assume_app_role)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory shared by request-scoped dependencies."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
