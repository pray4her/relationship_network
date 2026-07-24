import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import mfa_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.mfa_service import MfaSetupRequiredError, TenantMfaPolicyView

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def make_membership_view() -> MembershipView:
    return MembershipView(
        membership_id=MEMBERSHIP_ID,
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="owner",
    )


def make_authentication(*, with_membership: bool = True) -> Authentication:
    return Authentication(
        user=UserView(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="owner@example.com",
            display_name="Tenant Owner",
        ),
        membership=make_membership_view() if with_membership else None,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        renewed=False,
    )


def make_context(*, permissions: frozenset[str] | None = None) -> TenantContext:
    return TenantContext(
        authentication=make_authentication(),
        membership=make_membership_view(),
        permissions=permissions if permissions is not None else frozenset({"tenant:manage"}),
    )


def make_client(
    *,
    context: TenantContext | None = None,
    authentication: Authentication | None | object = ...,  # sentinel: keep real chain
) -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_db_session] = override_session
    if context is not None:

        def override_context() -> TenantContext:
            return context

        app.dependency_overrides[get_tenant_context] = override_context
    elif authentication is not ...:

        def override_authentication() -> Authentication | None:
            return cast("Authentication | None", authentication)

        app.dependency_overrides[get_authentication] = override_authentication
    return TestClient(app)


def test_current_tenant_returns_caller_tenant_and_role() -> None:
    # Given an authenticated tenant owner
    client = make_client(context=make_context())

    # When the current tenant is requested
    response = client.get("/tenants/current")

    # Then the tenant contract includes the caller's role
    assert response.status_code == 200
    assert response.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Acme 科技",
        "slug": "acme-1234abcd",
        "role": "owner",
    }


def test_current_tenant_requires_authentication() -> None:
    # Given an anonymous caller
    client = make_client(authentication=None)

    # When the current tenant is requested
    response = client.get("/tenants/current")

    # Then the caller is rejected with the pinned detail
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_current_tenant_forbidden_without_active_membership() -> None:
    # Given an authenticated user with no active membership
    client = make_client(authentication=make_authentication(with_membership=False))

    # When the current tenant is requested
    response = client.get("/tenants/current")

    # Then access is forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "no_active_membership"}


def test_update_mfa_policy_enables_enforcement(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding tenant:manage
    async def fake_set_policy(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        required: bool,
    ) -> TenantMfaPolicyView:
        assert tenant_id == TENANT_ID
        assert user_id is not None
        assert required is True
        return TenantMfaPolicyView(
            id=TENANT_ID,
            name="Acme 科技",
            slug="acme-1234abcd",
            mfa_required=True,
        )

    monkeypatch.setattr(mfa_service, "set_tenant_mfa_policy", fake_set_policy)
    client = make_client(context=make_context())

    # When the MFA policy is enabled
    response = client.put("/tenants/current/mfa-policy", json={"required": True})

    # Then the tenant view reflects the enforced policy
    assert response.status_code == 200
    assert response.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Acme 科技",
        "slug": "acme-1234abcd",
        "mfa_required": True,
    }


def test_update_mfa_policy_denied_without_tenant_manage() -> None:
    # Given a caller without tenant:manage
    client = make_client(context=make_context(permissions=frozenset()))

    # When the MFA policy is changed
    response = client.put("/tenants/current/mfa-policy", json={"required": True})

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_update_mfa_policy_requires_caller_mfa_to_enable(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting the caller has no MFA enabled
    async def fake_set_policy(_session: object, **_kwargs: object) -> TenantMfaPolicyView:
        raise MfaSetupRequiredError

    monkeypatch.setattr(mfa_service, "set_tenant_mfa_policy", fake_set_policy)
    client = make_client(context=make_context())

    # When the MFA policy is enabled
    response = client.put("/tenants/current/mfa-policy", json={"required": True})

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "mfa_setup_required"}
