import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_authentication,
    get_db_session,
)
from relationship_network_api.main import create_app


def make_authentication(*, with_membership: bool = True) -> Authentication:
    membership = (
        MembershipView(
            tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            tenant_name="Acme 科技",
            tenant_slug="acme-1234abcd",
            role="owner",
        )
        if with_membership
        else None
    )
    return Authentication(
        user=UserView(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="owner@example.com",
            display_name="Tenant Owner",
        ),
        membership=membership,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        renewed=False,
    )


def make_client(authentication: Authentication | None) -> TestClient:
    app = create_app(checks=())

    def override_authentication() -> Authentication | None:
        return authentication

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_authentication] = override_authentication
    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def test_current_tenant_returns_caller_tenant_and_role() -> None:
    # Given an authenticated tenant owner
    client = make_client(make_authentication())
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

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
    client = make_client(None)

    # When the current tenant is requested
    response = client.get("/tenants/current")

    # Then the caller is rejected with the pinned detail
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_current_tenant_forbidden_without_active_membership() -> None:
    # Given an authenticated user with no active membership
    client = make_client(make_authentication(with_membership=False))
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the current tenant is requested
    response = client.get("/tenants/current")

    # Then access is forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "no_active_membership"}
