import uuid
from collections.abc import AsyncIterator, Sequence
from typing import TypedDict, cast, final

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from relationship_network_api.config import load_app_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.main import create_app
from relationship_network_api.models import AuthSession, Tenant, TenantMembership, User

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.


@final
class RegistrationBody(TypedDict):
    user: dict[str, str]
    tenant: dict[str, str]
    role: str


@final
class Stack:
    def __init__(
        self,
        *,
        client: AsyncClient,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.client = client
        self.engine = engine
        self.session_factory = session_factory
        self.emails: list[str] = []
        self.tenant_ids: list[uuid.UUID] = []

    def track(self, *, email: str, tenant_id: uuid.UUID) -> None:
        self.emails.append(email)
        self.tenant_ids.append(tenant_id)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def stack() -> AsyncIterator[Stack]:
    settings = load_app_settings()
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app = create_app(checks=(), settings=settings, session_factory=session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_stack = Stack(client=client, engine=engine, session_factory=session_factory)
        try:
            yield test_stack
        finally:
            await cleanup(test_stack)
    await engine.dispose()


async def cleanup(stack: Stack) -> None:
    async with stack.session_factory() as session:
        user_ids = select(User.id).where(User.email.in_(stack.emails))
        _ = await session.execute(delete(AuthSession).where(AuthSession.user_id.in_(user_ids)))
        _ = await session.execute(
            delete(TenantMembership).where(TenantMembership.user_id.in_(user_ids))
        )
        _ = await session.execute(delete(User).where(User.email.in_(stack.emails)))
        _ = await session.execute(delete(Tenant).where(Tenant.id.in_(stack.tenant_ids)))
        await session.commit()


def unique_email() -> str:
    return f"itest-{uuid.uuid4().hex}@example.com"


async def register(
    stack: Stack,
    *,
    email: str,
    display_name: str = "集成用户",
) -> RegistrationBody:
    response = await stack.client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": display_name,
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    body = cast("RegistrationBody", response.json())
    tenant_id = uuid.UUID(body["tenant"]["id"])
    stack.track(email=email, tenant_id=tenant_id)
    return body


async def count_users(stack: Stack, emails: Sequence[str]) -> int:
    async with stack.session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.email.in_(emails))
        )
        return int(result.scalar_one())


async def count_tenants(stack: Stack) -> int:
    async with stack.session_factory() as session:
        result = await session.execute(select(func.count()).select_from(Tenant))
        return int(result.scalar_one())


@pytest.mark.anyio
@pytest.mark.integration
async def test_register_login_me_logout_flow(stack: Stack) -> None:
    # Given a fresh tenant owner registering through the API
    email = unique_email()
    registered = await register(stack, email=email)

    assert registered["role"] == "owner"
    assert registered["user"]["email"] == email

    # When the session cookie is used
    me = await stack.client.get("/auth/me")
    current = await stack.client.get("/tenants/current")

    # Then the identity and tenant contracts resolve through the membership
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email
    assert current.status_code == 200
    assert current.json()["role"] == "owner"
    assert current.json()["slug"] == registered["tenant"]["slug"]

    # When the session is terminated
    logout = await stack.client.post("/auth/logout")

    # Then the cookie no longer authenticates
    assert logout.status_code == 204
    assert (await stack.client.get("/auth/me")).status_code == 401
    assert (await stack.client.get("/tenants/current")).status_code == 401

    # When the owner logs back in
    login = await stack.client.post(
        "/auth/login",
        json={"email": email, "password": "integration-secret-1"},
    )

    # Then a fresh session authenticates again
    assert login.status_code == 200
    assert login.json()["tenant"]["slug"] == registered["tenant"]["slug"]
    assert (await stack.client.get("/auth/me")).status_code == 200


@pytest.mark.anyio
@pytest.mark.integration
async def test_login_rejects_unknown_email_and_wrong_password_identically(stack: Stack) -> None:
    # Given a registered tenant owner
    email = unique_email()
    _ = await register(stack, email=email)

    # When login fails for an unknown email and for a wrong password
    unknown = await stack.client.post(
        "/auth/login",
        json={"email": unique_email(), "password": "integration-secret-1"},
    )
    wrong = await stack.client.post(
        "/auth/login",
        json={"email": email, "password": "integration-secret-2"},
    )

    # Then both failures are indistinguishable
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "invalid_credentials"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_duplicate_email_registration_rolls_back_user_and_tenant(stack: Stack) -> None:
    # Given a successfully registered tenant owner
    email = unique_email()
    _ = await register(stack, email=email)
    tenants_before = await count_tenants(stack)

    # When a second registration reuses the email
    response = await stack.client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-9",
            "display_name": "冒名用户",
            "tenant_name": "冒名租户",
        },
    )

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "email_already_registered"}

    # And the failed transaction left no partial user or tenant behind
    assert await count_users(stack, [email]) == 1
    assert await count_tenants(stack) == tenants_before
