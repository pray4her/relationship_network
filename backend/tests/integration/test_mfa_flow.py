import uuid
from typing import cast

import pytest
from httpx import AsyncClient

from .auth_helpers import current_code, enable_mfa, login_pending, register
from .conftest import Stack, unique_email


@pytest.mark.anyio
@pytest.mark.integration
async def test_mfa_enrollment_and_login_challenge(stack: Stack) -> None:
    # Given a registered tenant owner
    async with AsyncClient(transport=stack.transport, base_url="http://test") as client:
        email = unique_email()
        registered = await register(client, email=email)
        stack.emails.append(email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
        )

        # When MFA is enrolled
        secret, recovery_codes = await enable_mfa(client)

        # Then the status reflects the enrollment
        status_response = await client.get("/auth/mfa/status")
        assert status_response.status_code == 200
        assert status_response.json() == {"enabled": True, "recovery_codes_remaining": 10}

        # And a second setup conflicts
        again = await client.post("/auth/mfa/setup")
        assert again.status_code == 409
        assert again.json() == {"detail": "mfa_already_enabled"}

        # When the owner logs in again
        _ = await client.post("/auth/logout")
        mfa_token = await login_pending(client, email=email)

        # Then no session cookie was issued yet
        assert (await client.get("/auth/me")).status_code == 401

        # And a wrong code is rejected while consuming an attempt
        wrong = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": "000000"},
        )
        assert wrong.status_code == 401
        assert wrong.json() == {"detail": "invalid_mfa_code"}
        assert (await client.get("/auth/me")).status_code == 401

        # When the correct code is submitted
        verified = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": current_code(secret)},
        )

        # Then a session is issued
        assert verified.status_code == 200
        assert verified.json()["role"] == "owner"
        assert (await client.get("/auth/me")).status_code == 200

        # And the used challenge cannot be replayed
        replayed = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": current_code(secret)},
        )
        assert replayed.status_code == 401
        assert replayed.json() == {"detail": "mfa_challenge_invalid"}

        # When logging in again and using a recovery code
        _ = await client.post("/auth/logout")
        mfa_token = await login_pending(client, email=email)
        recovered = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "recovery_code": recovery_codes[0]},
        )

        # Then the recovery code works exactly once
        assert recovered.status_code == 200
        assert (await client.get("/auth/me")).status_code == 200
        _ = await client.post("/auth/logout")
        mfa_token = await login_pending(client, email=email)
        reused = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "recovery_code": recovery_codes[0]},
        )
        assert reused.status_code == 401
        assert reused.json() == {"detail": "invalid_mfa_code"}

        # And the remaining count dropped
        _ = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": current_code(secret)},
        )
        status_response = await client.get("/auth/mfa/status")
        assert status_response.json()["recovery_codes_remaining"] == 9


@pytest.mark.anyio
@pytest.mark.integration
async def test_mfa_challenge_locks_out_after_five_failures(stack: Stack) -> None:
    # Given an enrolled owner starting a login challenge
    async with AsyncClient(transport=stack.transport, base_url="http://test") as client:
        email = unique_email()
        registered = await register(client, email=email)
        stack.emails.append(email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
        )
        secret, _ = await enable_mfa(client)
        _ = await client.post("/auth/logout")
        mfa_token = await login_pending(client, email=email)

        # When five wrong codes are submitted
        for _ in range(5):
            wrong = await client.post(
                "/auth/mfa/verify",
                json={"mfa_token": mfa_token, "code": "000000"},
            )
            assert wrong.status_code == 401
            assert wrong.json() == {"detail": "invalid_mfa_code"}

        # Then even the right code is rejected as an exhausted challenge
        exhausted = await client.post(
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": current_code(secret)},
        )
        assert exhausted.status_code == 401
        assert exhausted.json() == {"detail": "mfa_challenge_invalid"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_tenant_mfa_policy_enforcement(stack: Stack) -> None:
    # Given an owner with MFA and a member without MFA in one tenant
    owner = AsyncClient(transport=stack.transport, base_url="http://test")
    member = AsyncClient(transport=stack.transport, base_url="http://test")
    try:
        owner_email = unique_email()
        registered = await register(owner, email=owner_email)
        stack.emails.append(owner_email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
        )
        owner_secret, _ = await enable_mfa(owner)

        member_email = unique_email()
        created = await owner.post("/invitations", json={"email": member_email})
        assert created.status_code == 201
        _ = await register(
            member,
            email=member_email,
            invite_token=cast("str", created.json()["token"]),
        )
        stack.emails.append(member_email)

        # When the owner enforces the tenant MFA policy
        policy = await owner.put("/tenants/current/mfa-policy", json={"required": True})
        assert policy.status_code == 200
        assert policy.json()["mfa_required"] is True

        # Then the member loses access to tenant-scoped endpoints
        current = await member.get("/tenants/current")
        members = await member.get("/members")
        assert current.status_code == 403
        assert current.json() == {"detail": "mfa_required"}
        assert members.status_code == 403
        assert members.json() == {"detail": "mfa_required"}

        # But the member still reaches identity and MFA endpoints
        assert (await member.get("/auth/me")).status_code == 200
        assert (await member.get("/auth/mfa/status")).status_code == 200

        # And the owner with MFA keeps full access
        assert (await owner.get("/tenants/current")).status_code == 200
        assert (await owner.get("/members")).status_code == 200

        # When the member enrolls MFA
        member_secret, _ = await enable_mfa(member)

        # Then tenant access is restored
        assert (await member.get("/tenants/current")).status_code == 200

        # And neither the member nor the owner can disable MFA while enforced
        member_disable = await member.post(
            "/auth/mfa/disable",
            json={"code": current_code(member_secret)},
        )
        assert member_disable.status_code == 409
        assert member_disable.json() == {"detail": "mfa_required_by_tenant"}
        owner_disable = await owner.post(
            "/auth/mfa/disable",
            json={"code": current_code(owner_secret)},
        )
        assert owner_disable.status_code == 409
        assert owner_disable.json() == {"detail": "mfa_required_by_tenant"}

        # When the owner lifts the policy
        lifted = await owner.put("/tenants/current/mfa-policy", json={"required": False})
        assert lifted.status_code == 200
        assert lifted.json()["mfa_required"] is False

        # Then the member can disable MFA again
        disabled = await member.post(
            "/auth/mfa/disable",
            json={"code": current_code(member_secret)},
        )
        assert disabled.status_code == 204
    finally:
        await owner.aclose()
        await member.aclose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_enabling_policy_requires_caller_mfa(stack: Stack) -> None:
    # Given an owner without MFA
    async with AsyncClient(transport=stack.transport, base_url="http://test") as client:
        email = unique_email()
        registered = await register(client, email=email)
        stack.emails.append(email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
        )

        # When the policy is enabled
        policy = await client.put("/tenants/current/mfa-policy", json={"required": True})

        # Then the conflict is reported
        assert policy.status_code == 409
        assert policy.json() == {"detail": "mfa_setup_required"}


@pytest.mark.anyio
@pytest.mark.integration
async def test_enable_mfa_rejects_wrong_code(stack: Stack) -> None:
    # Given an owner with a pending setup
    async with AsyncClient(transport=stack.transport, base_url="http://test") as client:
        email = unique_email()
        registered = await register(client, email=email)
        stack.emails.append(email)
        stack.tenant_ids.append(
            uuid.UUID(cast("dict[str, dict[str, str]]", registered)["tenant"]["id"])
        )
        setup = await client.post("/auth/mfa/setup")
        assert setup.status_code == 200

        # When enabling with a wrong code
        enabled = await client.post("/auth/mfa/enable", json={"code": "000000"})

        # Then the code is rejected
        assert enabled.status_code == 401
        assert enabled.json() == {"detail": "invalid_mfa_code"}
