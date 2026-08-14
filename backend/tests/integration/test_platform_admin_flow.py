import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient

from relationship_network_api.config import load_app_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.main import create_app

from .auth_helpers import PASSWORD, current_code, enable_mfa, register
from .conftest import Stack, unique_email

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.


@pytest.fixture
async def admin_transport(stack: Stack) -> AsyncIterator[tuple[ASGITransport, str]]:
    """App instance whose settings allowlist a generated platform admin email."""
    _ = stack  # fixture ordering: the shared stack owns cleanup of created rows
    settings = load_app_settings()
    admin_email = unique_email()
    settings.platform_admin_emails = admin_email
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app = create_app(checks=(), settings=settings, session_factory=session_factory)
    try:
        yield ASGITransport(app=app), admin_email
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_platform_admin_flow(  # noqa: PLR0915
    stack: Stack,
    admin_transport: tuple[ASGITransport, str],
) -> None:
    transport, admin_email = admin_transport
    admin = AsyncClient(transport=transport, base_url="http://test")
    tenant_user = AsyncClient(transport=transport, base_url="http://test")
    try:
        # Given a platform administrator who belongs to no tenant
        registered = await register(admin, email=admin_email)
        stack.emails.append(admin_email)
        admin_user_id = cast("dict[str, str]", registered["user"])["id"]
        assert cast("dict[str, object]", registered["user"])["is_platform_admin"] is True
        assert registered["tenant"] is None
        assert registered["role"] is None

        # When the admin reads their identity
        me = await admin.get("/auth/me")

        # Then the identity carries no tenant context
        assert me.status_code == 200
        assert me.json()["user"]["is_platform_admin"] is True
        assert me.json()["tenant"] is None
        assert me.json()["permissions"] == []

        # And the management entry stays closed until MFA is enrolled
        denied = await admin.get("/admin/tenants")
        assert denied.status_code == 403
        assert denied.json() == {"detail": "mfa_required"}

        # When the admin enrolls MFA
        secret, _ = await enable_mfa(admin)

        # Then the entry still requires a fresh MFA-verified login
        challenged = await admin.get("/admin/tenants")
        assert challenged.status_code == 200

        # And the LLM configuration workbench uses the same global MFA gate
        llm_workspace = await admin.get("/admin/llm-configuration")
        assert llm_workspace.status_code == 200
        assert llm_workspace.json()["current"]["model"] == "x-ai/grok-4.5"
        assert llm_workspace.json()["active_attempt"] is None

        # And disabling MFA is refused for platform administrators
        disable = await admin.post(
            "/auth/mfa/disable",
            json={"code": current_code(secret)},
        )
        assert disable.status_code == 409
        assert disable.json() == {"detail": "mfa_required_for_platform_admin"}

        # Given a regular tenant user
        user_email = unique_email()
        user_registered = await register(tenant_user, email=user_email)
        stack.emails.append(user_email)
        user_tenant_id = cast("dict[str, str]", user_registered["tenant"])["id"]
        stack.tenant_ids.append(uuid.UUID(user_tenant_id))

        # When the tenant user probes the platform entry
        probe = await tenant_user.get("/admin/tenants")

        # Then tenant roles cannot derive platform admin rights
        assert probe.status_code == 403
        assert probe.json() == {"detail": "platform_admin_required"}
        llm_probe = await tenant_user.get("/admin/llm-configuration")
        assert llm_probe.status_code == 403
        assert llm_probe.json() == {"detail": "platform_admin_required"}

        # When the admin lists tenants
        listing = await admin.get("/admin/tenants")

        # Then the tenant is visible without the admin becoming a member of it
        assert listing.status_code == 200
        entry = next(
            tenant
            for tenant in listing.json()["tenants"]
            if tenant["slug"] == cast("dict[str, str]", user_registered["tenant"])["slug"]
        )
        assert entry["member_count"] == 1
        assert listing.json()["total"] >= 1

        # And the admin still has no tenant access
        members = await admin.get("/members")
        assert members.status_code == 403
        assert members.json() == {"detail": "no_active_membership"}

        # When the admin suspends the tenant
        updated = await admin.post(
            f"/admin/tenants/{user_tenant_id}/status",
            json={"status": "suspended"},
        )

        # Then the sensitive write succeeds and is audited
        assert updated.status_code == 200
        assert updated.json()["status"] == "suspended"
        events = await admin.get("/admin/audit-events")
        assert events.status_code == 200
        event = next(
            item
            for item in events.json()["events"]
            if item["action"] == "tenant.status_update" and item["target_id"] == user_tenant_id
        )
        assert event["actor_id"] == admin_user_id
        assert event["result"] == "success"
        assert event["created_at"]

        # And a re-login with the MFA challenge keeps working without membership
        _ = await admin.post("/auth/logout")
        pending = await admin.post(
            "/auth/login",
            json={"email": admin_email, "password": PASSWORD},
        )
        assert pending.json()["mfa_required"] is True
        verified = await admin.post(
            "/auth/mfa/verify",
            json={
                "mfa_token": cast("str", pending.json()["mfa_token"]),
                "code": current_code(secret),
            },
        )
        assert verified.status_code == 200
        assert verified.json()["tenant"] is None
        assert (await admin.get("/admin/tenants")).status_code == 200
    finally:
        await admin.aclose()
        await tenant_user.aclose()
