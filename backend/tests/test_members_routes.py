import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import membership_service, rbac_service, tenant_context
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.invitation_service import AlreadyInTenantError
from relationship_network_api.main import create_app
from relationship_network_api.membership_service import (
    MembershipNotFoundError,
    ProtectedOwnerError,
)
from relationship_network_api.rbac_service import MemberView

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def make_context(*, permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=MEMBERSHIP_ID,
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="owner",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                email="owner@example.com",
                display_name="Tenant Owner",
            ),
            membership=membership,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            renewed=False,
        ),
        membership=membership,
        permissions=permissions,
    )


def make_member_view(*, is_active: bool) -> MemberView:
    return MemberView(
        membership_id=MEMBERSHIP_ID,
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="member@example.com",
        display_name="Tenant Member",
        membership_role="member",
        is_active=is_active,
        role_ids=frozenset(),
    )


def make_client(context: TenantContext | None) -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_db_session] = override_session
    if context is None:

        def override_authentication() -> None:
            return None

        app.dependency_overrides[get_authentication] = override_authentication
    else:

        def override_context() -> TenantContext:
            return context

        app.dependency_overrides[get_tenant_context] = override_context
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_rls_context(monkeypatch: MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(tenant_context, "set_tenant_context", _noop)


def stub_reload(monkeypatch: MonkeyPatch, *, is_active: bool) -> None:
    async def fake_list_members(_session: object, *, tenant_id: uuid.UUID) -> list[MemberView]:
        assert tenant_id == TENANT_ID
        return [make_member_view(is_active=is_active)]

    monkeypatch.setattr(rbac_service, "list_members", fake_list_members)


def test_deactivate_member_returns_updated_view(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:manage
    calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def fake_deactivate(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> None:
        calls.append((tenant_id, membership_id))

    monkeypatch.setattr(membership_service, "deactivate_membership", fake_deactivate)
    stub_reload(monkeypatch, is_active=False)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the member is deactivated
    response = client.post(f"/members/{MEMBERSHIP_ID}/deactivate")

    # Then the service ran for the caller's tenant and the updated view is returned
    assert response.status_code == 200
    assert calls == [(TENANT_ID, MEMBERSHIP_ID)]
    assert response.json()["is_active"] is False


def test_deactivate_member_denied_without_members_manage() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When a member is deactivated
    response = client.post(f"/members/{MEMBERSHIP_ID}/deactivate")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_deactivate_member_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the membership in the caller's tenant
    async def fake_deactivate(_session: object, **_kwargs: object) -> None:
        raise MembershipNotFoundError

    monkeypatch.setattr(membership_service, "deactivate_membership", fake_deactivate)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When a missing or foreign membership is deactivated
    response = client.post(f"/members/{uuid.uuid4()}/deactivate")

    # Then the miss is reported without leaking existence
    assert response.status_code == 404
    assert response.json() == {"detail": "membership_not_found"}


def test_deactivate_owner_is_forbidden(monkeypatch: MonkeyPatch) -> None:
    # Given the service protecting the tenant owner
    async def fake_deactivate(_session: object, **_kwargs: object) -> None:
        raise ProtectedOwnerError

    monkeypatch.setattr(membership_service, "deactivate_membership", fake_deactivate)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the owner is deactivated
    response = client.post(f"/members/{MEMBERSHIP_ID}/deactivate")

    # Then the protection is reported
    assert response.status_code == 403
    assert response.json() == {"detail": "protected_owner"}


def test_activate_member_returns_updated_view(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:manage
    async def fake_activate(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> None:
        assert tenant_id == TENANT_ID
        assert membership_id == MEMBERSHIP_ID

    monkeypatch.setattr(membership_service, "activate_membership", fake_activate)
    stub_reload(monkeypatch, is_active=True)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the member is reactivated
    response = client.post(f"/members/{MEMBERSHIP_ID}/activate")

    # Then the updated view is returned
    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_activate_member_denied_without_members_manage() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When a member is activated
    response = client.post(f"/members/{MEMBERSHIP_ID}/activate")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_activate_member_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the membership
    async def fake_activate(_session: object, **_kwargs: object) -> None:
        raise MembershipNotFoundError

    monkeypatch.setattr(membership_service, "activate_membership", fake_activate)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When a missing or foreign membership is activated
    response = client.post(f"/members/{uuid.uuid4()}/activate")

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "membership_not_found"}


def test_activate_member_conflicts_when_user_active_in_other_tenant(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given the service enforcing the single-active-tenant invariant
    async def fake_activate(_session: object, **_kwargs: object) -> None:
        raise AlreadyInTenantError

    monkeypatch.setattr(membership_service, "activate_membership", fake_activate)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the member is reactivated while active in another tenant
    response = client.post(f"/members/{MEMBERSHIP_ID}/activate")

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "already_in_tenant"}


def test_remove_member_returns_no_content(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:manage
    async def fake_remove(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> None:
        assert tenant_id == TENANT_ID
        assert membership_id == MEMBERSHIP_ID

    monkeypatch.setattr(membership_service, "remove_membership", fake_remove)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the member is removed
    response = client.delete(f"/members/{MEMBERSHIP_ID}")

    # Then no content is returned
    assert response.status_code == 204
    assert response.content == b""


def test_remove_member_denied_without_members_manage() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When a member is removed
    response = client.delete(f"/members/{MEMBERSHIP_ID}")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_remove_member_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the membership
    async def fake_remove(_session: object, **_kwargs: object) -> None:
        raise MembershipNotFoundError

    monkeypatch.setattr(membership_service, "remove_membership", fake_remove)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When a missing or foreign membership is removed
    response = client.delete(f"/members/{uuid.uuid4()}")

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "membership_not_found"}


def test_remove_owner_is_forbidden(monkeypatch: MonkeyPatch) -> None:
    # Given the service protecting the tenant owner
    async def fake_remove(_session: object, **_kwargs: object) -> None:
        raise ProtectedOwnerError

    monkeypatch.setattr(membership_service, "remove_membership", fake_remove)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When the owner is removed
    response = client.delete(f"/members/{MEMBERSHIP_ID}")

    # Then the protection is reported
    assert response.status_code == 403
    assert response.json() == {"detail": "protected_owner"}


def test_member_lifecycle_endpoints_require_authentication() -> None:
    # Given an anonymous caller
    client = make_client(None)

    # When any lifecycle endpoint is called
    responses = [
        client.post(f"/members/{MEMBERSHIP_ID}/deactivate"),
        client.post(f"/members/{MEMBERSHIP_ID}/activate"),
        client.delete(f"/members/{MEMBERSHIP_ID}"),
    ]

    # Then the caller is rejected
    for response in responses:
        assert response.status_code == 401
        assert response.json() == {"detail": "not_authenticated"}
