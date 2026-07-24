import uuid
from collections.abc import AsyncIterator
from typing import final

import pytest
from httpx import ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from relationship_network_api.config import load_app_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.main import create_app
from relationship_network_api.models import Tenant, User

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.


@final
class Stack:
    """Shared integration stack: real engine/app plus handles for cleanup."""

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        transport: ASGITransport,
    ) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.transport = transport
        self.emails: list[str] = []
        self.tenant_ids: list[uuid.UUID] = []


@pytest.fixture
async def stack() -> AsyncIterator[Stack]:
    settings = load_app_settings()
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app = create_app(checks=(), settings=settings, session_factory=session_factory)
    test_stack = Stack(
        engine=engine,
        session_factory=session_factory,
        transport=ASGITransport(app=app),
    )
    try:
        yield test_stack
    finally:
        await cleanup(test_stack)
    await engine.dispose()


async def cleanup(stack: Stack) -> None:
    # Deleting users and tenants cascades to memberships, sessions, roles and
    # assignments; referential integrity enforcement is not subject to RLS.
    async with stack.session_factory() as session:
        _ = await session.execute(delete(User).where(User.email.in_(stack.emails)))
        _ = await session.execute(delete(Tenant).where(Tenant.id.in_(stack.tenant_ids)))
        await session.commit()


def unique_email() -> str:
    return f"itest-{uuid.uuid4().hex}@example.com"
