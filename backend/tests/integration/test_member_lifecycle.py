import uuid
from typing import cast, final

import pytest
from httpx import AsyncClient

from .conftest import Stack, unique_email

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.

PASSWORD = "integration-secret-1"


async def register(
    client: AsyncClient,
    *,
    email: str,
    invite_token: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": email,
        "password": PASSWORD,
        "display_name": "集成用户",
        "tenant_name": None,
    }
    if invite_token is not None:
        payload["invite_token"] = invite_token
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return cast("dict[str, object]", response.json())


@final
class TenantFixture:
    """An owner/member pair sharing one tenant, each with its own client."""

    def __init__(
        self,
        owner: AsyncClient,
        member: AsyncClient,
        *,
        member_email: str,
    ) -> None:
        self.owner = owner
        self.member = member
        self.member_email = member_email
        self.owner_membership_id: uuid.UUID | None = None
        self.member_membership_id: uuid.UUID | None = None


async def membership_ids(owner: AsyncClient) -> dict[str, str]:
    response = await owner.get("/members")
    assert response.status_code == 200
    return {
        cast("str", entry["membership_role"]): cast("str", entry["membership_id"])
        for entry in response.json()
    }


async def make_tenant(stack: Stack) -> TenantFixture:
    owner = AsyncClient(transport=stack.transport, base_url="http://test")
    member = AsyncClient(transport=stack.transport, base_url="http://test")
    owner_email = unique_email()
    registered = await register(owner, email=owner_email)
    stack.emails.append(owner_email)
    stack.tenant_ids.append(
        uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
    )
    member_email = unique_email()
    created = await owner.post("/invitations", json={"email": member_email})
    assert created.status_code == 201
    _ = await register(
        member, email=member_email, invite_token=cast("str", created.json()["token"])
    )
    stack.emails.append(member_email)
    fixture = TenantFixture(owner, member, member_email=member_email)
    ids = await membership_ids(owner)
    fixture.owner_membership_id = uuid.UUID(ids["owner"])
    fixture.member_membership_id = uuid.UUID(ids["member"])
    return fixture


@pytest.mark.anyio
@pytest.mark.integration
async def test_deactivate_blocks_session_and_activate_restores(stack: Stack) -> None:
    # Given a tenant with an owner and a member
    fixture = await make_tenant(stack)
    try:
        assert (await fixture.member.get("/members")).status_code == 403  # no members:read
        assert (await fixture.member.get("/auth/me")).status_code == 200

        # When the owner deactivates the member
        deactivated = await fixture.owner.post(
            f"/members/{fixture.member_membership_id}/deactivate"
        )

        # Then the membership view shows inactive
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        # And the member's session no longer reaches the tenant
        me = await fixture.member.get("/auth/me")
        members = await fixture.member.get("/members")
        assert me.status_code == 403
        assert me.json() == {"detail": "no_active_membership"}
        assert members.status_code == 403

        # And login is rejected like invalid credentials
        login = await fixture.member.post(
            "/auth/login",
            json={"email": fixture.member_email, "password": PASSWORD},
        )
        assert login.status_code == 401

        # When the owner reactivates the member
        activated = await fixture.owner.post(f"/members/{fixture.member_membership_id}/activate")

        # Then the membership is active and the session works again
        assert activated.status_code == 200
        assert activated.json()["is_active"] is True
        assert (await fixture.member.get("/auth/me")).status_code == 200
    finally:
        await fixture.owner.aclose()
        await fixture.member.aclose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_remove_member_deletes_membership(stack: Stack) -> None:
    # Given a tenant with an owner and a member
    fixture = await make_tenant(stack)
    try:
        # When the owner removes the member
        removed = await fixture.owner.delete(f"/members/{fixture.member_membership_id}")

        # Then the membership is gone and the session loses tenant access
        assert removed.status_code == 204
        members = await fixture.owner.get("/members")
        assert [entry["membership_role"] for entry in members.json()] == ["owner"]
        me = await fixture.member.get("/auth/me")
        assert me.status_code == 403
        assert me.json() == {"detail": "no_active_membership"}

        # And removing again reports the miss
        again = await fixture.owner.delete(f"/members/{fixture.member_membership_id}")
        assert again.status_code == 404
        assert again.json() == {"detail": "membership_not_found"}
    finally:
        await fixture.owner.aclose()
        await fixture.member.aclose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_owner_is_protected_from_lifecycle_operations(stack: Stack) -> None:
    # Given a tenant owner
    fixture = await make_tenant(stack)
    try:
        # When the owner targets their own membership
        deactivated = await fixture.owner.post(f"/members/{fixture.owner_membership_id}/deactivate")
        removed = await fixture.owner.delete(f"/members/{fixture.owner_membership_id}")

        # Then the protection is reported
        assert deactivated.status_code == 403
        assert deactivated.json() == {"detail": "protected_owner"}
        assert removed.status_code == 403
        assert removed.json() == {"detail": "protected_owner"}

        # And reactivating the owner remains a no-op success
        activated = await fixture.owner.post(f"/members/{fixture.owner_membership_id}/activate")
        assert activated.status_code == 200
        assert activated.json()["is_active"] is True
    finally:
        await fixture.owner.aclose()
        await fixture.member.aclose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_member_cannot_manage_members(stack: Stack) -> None:
    # Given a member without members:manage
    fixture = await make_tenant(stack)
    try:
        # When the member calls lifecycle endpoints
        responses = [
            await fixture.member.post(f"/members/{fixture.member_membership_id}/deactivate"),
            await fixture.member.post(f"/members/{fixture.member_membership_id}/activate"),
            await fixture.member.delete(f"/members/{fixture.member_membership_id}"),
        ]

        # Then every call is denied
        for response in responses:
            assert response.status_code == 403
            assert response.json() == {"detail": "permission_denied"}
    finally:
        await fixture.owner.aclose()
        await fixture.member.aclose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_activate_rejects_member_active_in_other_tenant(stack: Stack) -> None:
    # Given a tenant A member deactivated by the owner
    fixture = await make_tenant(stack)
    owner_b = AsyncClient(transport=stack.transport, base_url="http://test")
    try:
        deactivated = await fixture.owner.post(
            f"/members/{fixture.member_membership_id}/deactivate"
        )
        assert deactivated.status_code == 200

        # When the member accepts an invitation into tenant B
        owner_b_email = unique_email()
        registered_b = await register(owner_b, email=owner_b_email)
        stack.emails.append(owner_b_email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered_b)["tenant"]["id"])
        )
        created = await owner_b.post("/invitations", json={"email": fixture.member_email})
        assert created.status_code == 201
        accepted = await fixture.member.post(
            "/invitations/accept",
            json={"token": cast("str", created.json()["token"])},
        )
        assert accepted.status_code == 200

        # Then reactivating the old membership in tenant A conflicts
        reactivated = await fixture.owner.post(f"/members/{fixture.member_membership_id}/activate")
        assert reactivated.status_code == 409
        assert reactivated.json() == {"detail": "already_in_tenant"}
    finally:
        await fixture.owner.aclose()
        await fixture.member.aclose()
        await owner_b.aclose()
