from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from relationship_network_api.config import DatabaseSettings


def create_engine_from_settings(settings: DatabaseSettings) -> AsyncEngine:
    """Build the async SQLAlchemy engine for the configured database."""
    return create_async_engine(str(settings.database_url), pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory shared by request-scoped dependencies."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
