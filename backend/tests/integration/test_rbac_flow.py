import uuid
from collections.abc import AsyncIterator
from typing import cast, final

import pytest
from httpx import AsyncClient

from relationship_network_api.models import TenantMembership, User
from relationship_network_api.security import hash_password
from relationship_network_api.tenant_context import set_tenant_context

from .conftest import Stack, unique_email

MEMBER_PASSWORD = "member-secret-1"


@final
class Clients:
    def __init__(self, owner: AsyncClient, member: AsyncClient, outsider: AsyncClient) -> None:
        self.owner = owner
        self.member = member
        self.outsider = outsider


@pytest.fixture
async def clients(stack: Stack) -> AsyncIterator[Clients]:
    async with (
        AsyncClient(transport=stack.transport, base_url="http://test") as owner,
        AsyncClient(transport=stack.transport, base_url="http://test") as member,
        AsyncClient(transport=stack.transport, base_url="http://test") as outsider,
    ):
        yield Clients(owner=owner, member=member, outsider=outsider)


async def register_owner(stack: Stack, client: AsyncClient) -> dict[str, object]:
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "集成租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    body = cast("dict[str, object]", response.json())
    tenant = cast("dict[str, str]", body["tenant"])
    stack.emails.append(email)
    stack.tenant_ids.append(uuid.UUID(tenant["id"]))
    return body


async def add_member(stack: Stack, *, tenant_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    """Insert a member user and membership directly, as no invite flow exists yet."""
    email = unique_email()
    membership_id = uuid.uuid4()
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name="集成成员",
            password_hash=hash_password(MEMBER_PASSWORD),
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            TenantMembership(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=user.id,
                role="member",
                is_active=True,
            )
        )
        await session.commit()
    stack.emails.append(email)
    return email, membership_id


@pytest.mark.anyio
@pytest.mark.integration
async def test_rbac_role_assignment_and_permission_union_flow(
    stack: Stack, clients: Clients
) -> None:
    # Given a tenant owner and a plain member of the same tenant
    owner_body = await register_owner(stack, clients.owner)
    tenant_id = uuid.UUID(cast("dict[str, str]", owner_body["tenant"])["id"])
    member_email, membership_id = await add_member(stack, tenant_id=tenant_id)
    login = await clients.member.post(
        "/auth/login",
        json={"email": member_email, "password": MEMBER_PASSWORD},
    )
    assert login.status_code == 200

    # Then the owner implicitly holds every permission without any role
    assert (await clients.owner.get("/permissions")).status_code == 200
    assert (await clients.owner.get("/roles")).status_code == 200
    assert (await clients.owner.get("/members")).status_code == 200

    # And the member starts with no permissions
    denied = await clients.member.get("/roles")
    assert denied.status_code == 403
    assert denied.json() == {"detail": "permission_denied"}

    # When the owner creates a viewer role and assigns it to the member
    created = await clients.owner.post(
        "/roles",
        json={"name": "查看者", "description": "只读角色", "permissions": ["roles:read"]},
    )
    assert created.status_code == 201
    viewer_role_id = created.json()["id"]
    assigned = await clients.owner.put(
        f"/members/{membership_id}/roles",
        json={"role_ids": [viewer_role_id]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["role_ids"] == [viewer_role_id]

    # Then the assignment takes effect on the member's next request
    assert (await clients.member.get("/roles")).status_code == 200
    assert (await clients.member.get("/members")).status_code == 403

    # When the role's metadata is edited without touching its permissions
    renamed = await clients.owner.patch(
        f"/roles/{viewer_role_id}",
        json={"description": "更新后的描述"},
    )

    # Then the permissions survive the metadata-only update
    assert renamed.status_code == 200
    assert renamed.json()["permissions"] == ["roles:read"]
    assert (await clients.member.get("/roles")).status_code == 200

    # When a second role with a disjoint permission is also assigned
    auditor = await clients.owner.post(
        "/roles",
        json={"name": "审计员", "description": "", "permissions": ["members:read"]},
    )
    assert auditor.status_code == 201
    auditor_role_id = auditor.json()["id"]
    reassigned = await clients.owner.put(
        f"/members/{membership_id}/roles",
        json={"role_ids": [viewer_role_id, auditor_role_id]},
    )
    assert reassigned.status_code == 200

    # Then the member's permissions are the union of both roles
    assert (await clients.member.get("/roles")).status_code == 200
    assert (await clients.member.get("/members")).status_code == 200

    # When the owner revokes a permission from one role
    updated = await clients.owner.patch(
        f"/roles/{viewer_role_id}",
        json={"permissions": []},
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == []

    # Then the revocation takes effect on the next request
    assert (await clients.member.get("/roles")).status_code == 403
    assert (await clients.member.get("/members")).status_code == 200

    # When the remaining role is deactivated
    deactivated = await clients.owner.patch(
        f"/roles/{auditor_role_id}",
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # Then its permissions no longer apply
    assert (await clients.member.get("/members")).status_code == 403


@pytest.mark.anyio
@pytest.mark.integration
async def test_owner_keeps_all_permissions_even_with_roles_unassigned(
    stack: Stack, clients: Clients
) -> None:
    # Given a tenant owner whose membership has no roles assigned
    _ = await register_owner(stack, clients.owner)
    members = await clients.owner.get("/members")
    assert members.status_code == 200
    owner_membership_id = next(
        member["membership_id"] for member in members.json() if member["membership_role"] == "owner"
    )
    cleared = await clients.owner.put(
        f"/members/{owner_membership_id}/roles",
        json={"role_ids": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["role_ids"] == []

    # Then the owner still holds every tenant permission
    assert (await clients.owner.get("/permissions")).status_code == 200
    assert (await clients.owner.get("/roles")).status_code == 200
    assert (await clients.owner.get("/members")).status_code == 200
    created = await clients.owner.post("/roles", json={"name": "验证", "permissions": []})
    assert created.status_code == 201


@pytest.mark.anyio
@pytest.mark.integration
async def test_rbac_rejects_cross_tenant_access(stack: Stack, clients: Clients) -> None:
    # Given two tenants, each with a role and a member
    owner_body = await register_owner(stack, clients.owner)
    tenant_id = uuid.UUID(cast("dict[str, str]", owner_body["tenant"])["id"])
    _, membership_id = await add_member(stack, tenant_id=tenant_id)
    created = await clients.owner.post(
        "/roles",
        json={"name": "查看者", "description": "", "permissions": ["roles:read"]},
    )
    assert created.status_code == 201
    role_id = created.json()["id"]
    _ = await register_owner(stack, clients.outsider)

    # When the outsider touches the other tenant's role or membership
    patched = await clients.outsider.patch(f"/roles/{role_id}", json={"name": "越权"})
    assigned = await clients.outsider.put(
        f"/members/{membership_id}/roles",
        json={"role_ids": []},
    )
    created_foreign = await clients.outsider.post(
        "/roles",
        json={"name": "越权", "description": "", "permissions": ["roles:read"]},
    )

    # Then foreign rows are invisible and the outsider's own tenant works
    assert patched.status_code == 404
    assert patched.json() == {"detail": "role_not_found"}
    assert assigned.status_code == 404
    assert assigned.json() == {"detail": "membership_not_found"}
    assert created_foreign.status_code == 201

    # And the original role is untouched
    roles = await clients.owner.get("/roles")
    assert [role["name"] for role in roles.json()] == ["查看者"]


@pytest.mark.anyio
@pytest.mark.integration
async def test_rbac_validates_inputs(stack: Stack, clients: Clients) -> None:
    # Given a tenant owner
    _ = await register_owner(stack, clients.owner)

    # When a role uses a permission outside the system catalog
    unknown = await clients.owner.post(
        "/roles",
        json={"name": "越界", "description": "", "permissions": ["roles:fly"]},
    )

    # Then it is rejected
    assert unknown.status_code == 422
    assert unknown.json() == {"detail": "unknown_permission"}

    # When a duplicate role name is used
    first = await clients.owner.post("/roles", json={"name": "重复", "permissions": []})
    second = await clients.owner.post("/roles", json={"name": "重复", "permissions": []})

    # Then the conflict is reported
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "duplicate_role_name"}
