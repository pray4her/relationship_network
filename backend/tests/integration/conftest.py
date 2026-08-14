import asyncio
import socket
import uuid
from collections.abc import AsyncIterator
from typing import final

import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from relationship_network_api.config import load_app_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.fake_openrouter import app as fake_openrouter_app
from relationship_network_api.fake_openrouter import reset_fake_openrouter
from relationship_network_api.fake_search_base import app as fake_search_base_app
from relationship_network_api.fake_search_base import reset_fake_search_base
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
    from sqlalchemy.exc import DBAPIError  # noqa: PLC0415

    async with stack.session_factory() as session:
        try:
            _ = await session.execute(delete(Tenant).where(Tenant.id.in_(stack.tenant_ids)))
            await session.commit()
        except DBAPIError:
            await session.rollback()
        try:
            _ = await session.execute(delete(User).where(User.email.in_(stack.emails)))
            await session.commit()
        except DBAPIError:
            await session.rollback()


def unique_email() -> str:
    return f"itest-{uuid.uuid4().hex}@example.com"


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
async def fake_openrouter_base_url() -> AsyncIterator[str]:
    reset_fake_openrouter()
    port = _unused_port()
    server = uvicorn.Server(
        uvicorn.Config(fake_openrouter_app, host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            message = "fake OpenRouter failed to start"
            raise RuntimeError(message)
        yield f"http://127.0.0.1:{port}/api/v1"
    finally:
        server.should_exit = True
        await task
        reset_fake_openrouter()


@pytest.fixture
async def fake_search_base_base_url() -> AsyncIterator[str]:
    reset_fake_search_base()
    port = _unused_port()
    server = uvicorn.Server(
        uvicorn.Config(fake_search_base_app, host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            message = "fake search base failed to start"
            raise RuntimeError(message)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task
        reset_fake_search_base()


@pytest.fixture
async def pipeline(
    stack: Stack,
    fake_openrouter_base_url: str,
) -> AsyncIterator[object]:
    from .openrouter_pipeline import (  # noqa: PLC0415
        FAKE_API_KEY,
        TEST_RAW_RESPONSE_KEYS,
        Pipeline,
        restore_current_version,
        snapshot_current_version,
    )

    settings = load_app_settings()
    admin_email = unique_email()
    settings.platform_admin_emails = admin_email
    settings.openrouter_api_key = SecretStr(FAKE_API_KEY)
    settings.openrouter_base_url = fake_openrouter_base_url
    settings.llm_raw_response_keys = SecretStr(TEST_RAW_RESPONSE_KEYS)
    settings.llm_raw_response_active_key_id = "local-v1"
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app = create_app(checks=(), settings=settings, session_factory=session_factory)
    transport = ASGITransport(app=app)
    admin = AsyncClient(transport=transport, base_url="http://test")
    original_current = await snapshot_current_version(settings)
    try:
        yield Pipeline(
            stack=stack,
            settings=settings,
            transport=transport,
            admin=admin,
            admin_email=admin_email,
            engine=engine,
            session_factory=session_factory,
        )
    finally:
        await restore_current_version(settings, original_current)
        await admin.aclose()
        await engine.dispose()
