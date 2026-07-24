import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from relationship_network_api.models import Role, TenantInvitation, TenantMembership
from relationship_network_api.tenant_context import set_tenant_context

from .conftest import Stack, unique_email

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_tenant(stack: Stack, client: AsyncClient) -> tuple[uuid.UUID, str]:
    """Register a tenant through the API and create one role; returns tenant and role id."""
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "隔离租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    created = await client.post(
        "/roles",
        json={"name": "查看者", "description": "", "permissions": ["roles:read"]},
    )
    assert created.status_code == 201
    return tenant_id, cast("str", created.json()["id"])


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_scopes_reads_to_the_current_tenant(stack: Stack, client: AsyncClient) -> None:
    # Given two tenants that each own a role
    tenant_a, role_a = await register_tenant(stack, client)
    tenant_b, role_b = await register_tenant(stack, client)

    # When tenant A queries the roles table without any tenant filter
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        result = await session.execute(select(Role.id))
        visible = {row[0] for row in result.all()}

    # Then row level security still hides the other tenant's rows
    assert uuid.UUID(role_a) in visible
    assert uuid.UUID(role_b) not in visible

    # When tenant B runs the same unfiltered query
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        result = await session.execute(select(Role.id))
        visible = {row[0] for row in result.all()}

    # Then only tenant B rows are visible
    assert uuid.UUID(role_b) in visible
    assert uuid.UUID(role_a) not in visible


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_blocks_cross_tenant_writes(stack: Stack, client: AsyncClient) -> None:
    # Given two tenants that each own a role
    tenant_a, _ = await register_tenant(stack, client)
    tenant_b, role_b = await register_tenant(stack, client)

    # When tenant A tries to insert a role row owned by tenant B
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        session.add(
            Role(
                id=uuid.uuid4(),
                tenant_id=tenant_b,
                name="越权角色",
                description="",
                is_active=True,
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

    # When tenant A tries to update or delete tenant B's role
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        updated = cast(
            "CursorResult[object]",
            await session.execute(
                text("UPDATE roles SET name = '越权' WHERE id = :role_id"),
                {"role_id": role_b},
            ),
        )
        deleted = cast(
            "CursorResult[object]",
            await session.execute(
                text("DELETE FROM roles WHERE id = :role_id"),
                {"role_id": role_b},
            ),
        )
        await session.rollback()

    # Then no cross-tenant row is touched
    assert updated.rowcount == 0
    assert deleted.rowcount == 0

    # And tenant B's role is still intact
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        result = await session.execute(select(Role.name).where(Role.id == uuid.UUID(role_b)))
        assert result.scalar_one() == "查看者"


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_denies_all_access_without_tenant_context(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a tenant with a role
    _ = await register_tenant(stack, client)

    # When a query omits the tenant filter and no session context is set
    async with stack.session_factory() as session:
        result = await session.execute(select(Role.id))
        visible = result.all()
        memberships = (await session.execute(select(TenantMembership.id))).all()

    # Then row level security denies every tenant-scoped row
    assert visible == []
    assert memberships == []


async def create_invitation(stack: Stack, client: AsyncClient) -> str:
    """Create one invitation in the caller's tenant; returns the invitation id."""
    invitee = unique_email()
    created = await client.post("/invitations", json={"email": invitee})
    assert created.status_code == 201
    stack.emails.append(invitee)
    return cast("str", created.json()["invitation"]["id"])


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_scopes_invitations_to_the_current_tenant(
    stack: Stack, client: AsyncClient
) -> None:
    # Given two tenants that each own an invitation
    tenant_a, _ = await register_tenant(stack, client)
    invitation_a = await create_invitation(stack, client)
    tenant_b, _ = await register_tenant(stack, client)
    invitation_b = await create_invitation(stack, client)

    # When tenant A queries the invitations table without any tenant filter
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        result = await session.execute(select(TenantInvitation.id))
        visible = {row[0] for row in result.all()}

    # Then row level security hides the other tenant's rows
    assert uuid.UUID(invitation_a) in visible
    assert uuid.UUID(invitation_b) not in visible

    # When tenant B runs the same unfiltered query
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        result = await session.execute(select(TenantInvitation.id))
        visible = {row[0] for row in result.all()}

    # Then only tenant B rows are visible
    assert uuid.UUID(invitation_b) in visible
    assert uuid.UUID(invitation_a) not in visible

    # And without any context nothing is visible
    async with stack.session_factory() as session:
        result = await session.execute(select(TenantInvitation.id))
        assert result.all() == []
