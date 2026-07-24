import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from relationship_network_api.models import TenantInvitation
from relationship_network_api.tenant_context import set_tenant_context

from .conftest import Stack, unique_email

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.

PASSWORD = "integration-secret-1"


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_owner(stack: Stack, client: AsyncClient) -> tuple[str, uuid.UUID]:
    """Register a fresh tenant owner; returns the email and tenant id."""
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return email, tenant_id


async def create_invitation(client: AsyncClient, *, email: str) -> dict[str, object]:
    response = await client.post("/invitations", json={"email": email})
    assert response.status_code == 201
    return cast("dict[str, object]", response.json())


@pytest.mark.anyio
@pytest.mark.integration
async def test_invite_register_accept_lifecycle(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant owner inviting a new email
    _, tenant_id = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    token = cast("str", created["token"])
    assert cast("str", created["invite_url"]).endswith(f"/invite/{token}")
    invitation = cast("dict[str, object]", created["invitation"])
    assert invitation["status"] == "pending"
    assert invitation["email"] == invitee_email

    # And the invitation is listed for the tenant
    listed = await client.get("/invitations")
    assert listed.status_code == 200
    assert [entry["id"] for entry in listed.json()] == [invitation["id"]]

    # When the invitation is previewed anonymously
    preview = await client.get("/invitations/preview", params={"token": token})

    # Then the public view resolves without authentication
    assert preview.status_code == 200
    assert preview.json()["email"] == invitee_email
    assert preview.json()["tenant_name"]

    # When the invitee registers with the token
    async with AsyncClient(transport=stack.transport, base_url="http://test") as invitee:
        registered = await invitee.post(
            "/auth/register",
            json={
                "email": invitee_email,
                "password": PASSWORD,
                "display_name": "受邀用户",
                "tenant_name": None,
                "invite_token": token,
            },
        )

        # Then the invitee joins the issuing tenant as a member without a new tenant
        assert registered.status_code == 201
        assert registered.json()["role"] == "member"
        assert registered.json()["tenant"]["id"] == str(tenant_id)
        stack.emails.append(invitee_email)

        # And the session resolves into the issuing tenant
        me = await invitee.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["tenant"]["id"] == str(tenant_id)
        assert me.json()["role"] == "member"

        # When the same token is replayed
        replayed = await invitee.post("/invitations/accept", json={"token": token})

        # Then the used invitation is invalid
        assert replayed.status_code == 404
        assert replayed.json() == {"detail": "invitation_invalid"}

    # And the owner sees the invitation as accepted
    accepted = await client.get("/invitations")
    assert accepted.json()[0]["status"] == "accepted"


@pytest.mark.anyio
@pytest.mark.integration
async def test_expired_invitation_is_invalid(stack: Stack, client: AsyncClient) -> None:
    # Given an invitation whose expiry is moved into the past
    _, tenant_id = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    token = cast("str", created["token"])
    invitation_id = uuid.UUID(cast("dict[str, str]", created["invitation"])["id"])
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        _ = await session.execute(
            update(TenantInvitation)
            .where(TenantInvitation.id == invitation_id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    stack.emails.append(invitee_email)

    # When the invitation is previewed or accepted
    preview = await client.get("/invitations/preview", params={"token": token})
    accepted = await client.post("/invitations/accept", json={"token": token})

    # Then both fail uniformly
    assert preview.status_code == 404
    assert preview.json() == {"detail": "invitation_invalid"}
    assert accepted.status_code == 404
    assert accepted.json() == {"detail": "invitation_invalid"}

    # And registering with the expired token fails uniformly too
    registered = await client.post(
        "/auth/register",
        json={
            "email": invitee_email,
            "password": PASSWORD,
            "display_name": "受邀用户",
            "tenant_name": None,
            "invite_token": token,
        },
    )
    assert registered.status_code == 404
    assert registered.json() == {"detail": "invitation_invalid"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_revoked_invitation_is_invalid(stack: Stack, client: AsyncClient) -> None:
    # Given an invitation that gets revoked
    _, _ = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    token = cast("str", created["token"])
    invitation_id = cast("dict[str, str]", created["invitation"])["id"]
    stack.emails.append(invitee_email)

    revoked = await client.post(f"/invitations/{invitation_id}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    # When the invitation is previewed or used for registration
    preview = await client.get("/invitations/preview", params={"token": token})
    registered = await client.post(
        "/auth/register",
        json={
            "email": invitee_email,
            "password": PASSWORD,
            "display_name": "受邀用户",
            "tenant_name": None,
            "invite_token": token,
        },
    )

    # Then both fail uniformly
    assert preview.status_code == 404
    assert preview.json() == {"detail": "invitation_invalid"}
    assert registered.status_code == 404
    assert registered.json() == {"detail": "invitation_invalid"}

    # And revoking again is idempotent
    again = await client.post(f"/invitations/{invitation_id}/revoke")
    assert again.status_code == 200
    assert again.json()["status"] == "revoked"


@pytest.mark.anyio
@pytest.mark.integration
async def test_register_with_invite_rejects_email_mismatch(
    stack: Stack, client: AsyncClient
) -> None:
    # Given an invitation for one email
    _, _ = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    stack.emails.append(invitee_email)

    # When a different email registers with the token
    other_email = unique_email()
    registered = await client.post(
        "/auth/register",
        json={
            "email": other_email,
            "password": PASSWORD,
            "display_name": "冒名用户",
            "tenant_name": None,
            "invite_token": cast("str", created["token"]),
        },
    )
    stack.emails.append(other_email)

    # Then the mismatch is reported
    assert registered.status_code == 403
    assert registered.json() == {"detail": "invitation_email_mismatch"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_accept_invitation_rejects_user_already_in_tenant(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a second tenant owner invited into the first tenant
    _, _ = await register_owner(stack, client)
    async with AsyncClient(transport=stack.transport, base_url="http://test") as other:
        other_email, _ = await register_owner(stack, other)
        created = await create_invitation(client, email=other_email)

        # When the second owner accepts the invitation
        accepted = await other.post(
            "/invitations/accept",
            json={"token": cast("str", created["token"])},
        )

        # Then the conflict is reported
        assert accepted.status_code == 409
        assert accepted.json() == {"detail": "already_in_tenant"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_invitation_endpoints_enforce_rbac(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant owner and an invited member without roles
    _, _ = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    async with AsyncClient(transport=stack.transport, base_url="http://test") as member:
        registered = await member.post(
            "/auth/register",
            json={
                "email": invitee_email,
                "password": PASSWORD,
                "display_name": "受邀用户",
                "tenant_name": None,
                "invite_token": cast("str", created["token"]),
            },
        )
        assert registered.status_code == 201
        stack.emails.append(invitee_email)

        # When the member touches invitation management endpoints
        responses = [
            await member.post("/invitations", json={"email": unique_email()}),
            await member.get("/invitations"),
            await member.post(f"/invitations/{uuid.uuid4()}/revoke"),
        ]

        # Then every call is denied for lack of permission
        for response in responses:
            assert response.status_code == 403
            assert response.json() == {"detail": "permission_denied"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_duplicate_pending_invitation_conflicts(stack: Stack, client: AsyncClient) -> None:
    # Given a pending invitation for an email
    _, _ = await register_owner(stack, client)
    invitee_email = unique_email()
    _ = await create_invitation(client, email=invitee_email)
    stack.emails.append(invitee_email)

    # When a second invitation is created for the same email
    duplicate = await client.post("/invitations", json={"email": invitee_email})

    # Then the conflict is reported
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "invitation_already_pending"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_inviting_active_member_conflicts(stack: Stack, client: AsyncClient) -> None:
    # Given an invited member who already joined
    _, _ = await register_owner(stack, client)
    invitee_email = unique_email()
    created = await create_invitation(client, email=invitee_email)
    async with AsyncClient(transport=stack.transport, base_url="http://test") as member:
        registered = await member.post(
            "/auth/register",
            json={
                "email": invitee_email,
                "password": PASSWORD,
                "display_name": "受邀用户",
                "tenant_name": None,
                "invite_token": cast("str", created["token"]),
            },
        )
        assert registered.status_code == 201
    stack.emails.append(invitee_email)

    # When the member is invited again
    duplicate = await client.post("/invitations", json={"email": invitee_email})

    # Then the conflict is reported
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "email_already_member"}
