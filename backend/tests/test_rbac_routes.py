import uuid
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import rbac_service, tenant_context
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.rbac_service import (
    SYSTEM_PERMISSIONS,
    DuplicateRoleNameError,
    MembershipNotFoundError,
    MemberView,
    RoleNotFoundError,
    RoleView,
    UnknownPermissionError,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
ROLE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def make_context(*, permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=MEMBERSHIP_ID,
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="member",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                email="member@example.com",
                display_name="Tenant Member",
            ),
            membership=membership,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            renewed=False,
        ),
        membership=membership,
        permissions=permissions,
    )


def make_role_view(
    *,
    is_active: bool = True,
    permissions: frozenset[str] | None = None,
) -> RoleView:
    return RoleView(
        id=ROLE_ID,
        name="运营",
        description="运营角色",
        is_active=is_active,
        permissions=permissions if permissions is not None else frozenset({"roles:read"}),
    )


def make_member_view(*, role_ids: frozenset[uuid.UUID] | None = None) -> MemberView:
    return MemberView(
        membership_id=MEMBERSHIP_ID,
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="member@example.com",
        display_name="Tenant Member",
        membership_role="member",
        is_active=True,
        role_ids=role_ids if role_ids is not None else frozenset(),
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


def test_list_permissions_allowed_with_roles_read() -> None:
    # Given a caller holding roles:read
    client = make_client(make_context(permissions=frozenset({"roles:read"})))

    # When the permission catalog is requested
    response = client.get("/permissions")

    # Then the system-defined catalog is returned
    assert response.status_code == 200
    assert response.json() == [
        {"code": code, "description": SYSTEM_PERMISSIONS[code]}
        for code in sorted(SYSTEM_PERMISSIONS)
    ]


def test_list_permissions_denied_without_roles_read() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When the permission catalog is requested
    response = client.get("/permissions")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_list_roles_allowed_with_roles_read(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding roles:read and one stored role
    async def fake_list_roles(_session: object, *, tenant_id: uuid.UUID) -> list[RoleView]:
        assert tenant_id == TENANT_ID
        return [make_role_view()]

    monkeypatch.setattr(rbac_service, "list_roles", fake_list_roles)
    client = make_client(make_context(permissions=frozenset({"roles:read"})))

    # When the roles are listed
    response = client.get("/roles")

    # Then the tenant roles are returned
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(ROLE_ID),
            "name": "运营",
            "description": "运营角色",
            "is_active": True,
            "permissions": ["roles:read"],
        }
    ]


def test_list_roles_denied_without_roles_read() -> None:
    # Given a caller without roles:read
    client = make_client(make_context(permissions=frozenset()))

    # When the roles are listed
    response = client.get("/roles")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_create_role_allowed_with_roles_manage(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding roles:manage
    async def fake_create_role(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        name: str,
        **_kwargs: object,
    ) -> RoleView:
        assert tenant_id == TENANT_ID
        assert name == "运营"
        return make_role_view()

    monkeypatch.setattr(rbac_service, "create_role", fake_create_role)
    client = make_client(make_context(permissions=frozenset({"roles:manage"})))

    # When a role is created
    response = client.post(
        "/roles",
        json={"name": "运营", "description": "运营角色", "permissions": ["roles:read"]},
    )

    # Then the role is returned
    assert response.status_code == 201
    assert response.json()["name"] == "运营"
    assert response.json()["permissions"] == ["roles:read"]


def test_create_role_denied_without_roles_manage() -> None:
    # Given a caller holding only roles:read
    client = make_client(make_context(permissions=frozenset({"roles:read"})))

    # When a role is created
    response = client.post("/roles", json={"name": "运营", "permissions": []})

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_create_role_rejects_unknown_permission(monkeypatch: MonkeyPatch) -> None:
    # Given the service rejecting a non-catalog permission
    async def fake_create_role(_session: object, **_kwargs: object) -> RoleView:
        raise UnknownPermissionError(frozenset({"roles:fly"}))

    monkeypatch.setattr(rbac_service, "create_role", fake_create_role)
    client = make_client(make_context(permissions=frozenset({"roles:manage"})))

    # When the role uses an unknown permission
    response = client.post("/roles", json={"name": "运营", "permissions": ["roles:fly"]})

    # Then the request is rejected
    assert response.status_code == 422
    assert response.json() == {"detail": "unknown_permission"}


def test_create_role_conflict_on_duplicate_name(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting a duplicate role name
    async def fake_create_role(_session: object, **_kwargs: object) -> RoleView:
        raise DuplicateRoleNameError

    monkeypatch.setattr(rbac_service, "create_role", fake_create_role)
    client = make_client(make_context(permissions=frozenset({"roles:manage"})))

    # When a duplicate role is created
    response = client.post("/roles", json={"name": "运营", "permissions": []})

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "duplicate_role_name"}


def test_update_role_allowed_with_roles_manage(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding roles:manage
    async def fake_update_role(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
        **_kwargs: object,
    ) -> RoleView:
        assert tenant_id == TENANT_ID
        assert role_id == ROLE_ID
        return make_role_view(is_active=False)

    monkeypatch.setattr(rbac_service, "update_role", fake_update_role)
    client = make_client(make_context(permissions=frozenset({"roles:manage"})))

    # When the role is deactivated
    response = client.patch(f"/roles/{ROLE_ID}", json={"is_active": False})

    # Then the updated role is returned
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_update_role_denied_without_roles_manage() -> None:
    # Given a caller holding only roles:read
    client = make_client(make_context(permissions=frozenset({"roles:read"})))

    # When the role is updated
    response = client.patch(f"/roles/{ROLE_ID}", json={"is_active": False})

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_update_role_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the role in the caller's tenant
    async def fake_update_role(_session: object, **_kwargs: object) -> RoleView:
        raise RoleNotFoundError

    monkeypatch.setattr(rbac_service, "update_role", fake_update_role)
    client = make_client(make_context(permissions=frozenset({"roles:manage"})))

    # When a missing or foreign role is updated
    response = client.patch(f"/roles/{uuid.uuid4()}", json={"name": "新名字"})

    # Then the miss is reported without leaking existence
    assert response.status_code == 404
    assert response.json() == {"detail": "role_not_found"}


def test_list_members_allowed_with_members_read(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:read
    async def fake_list_members(_session: object, *, tenant_id: uuid.UUID) -> list[MemberView]:
        assert tenant_id == TENANT_ID
        return [make_member_view()]

    monkeypatch.setattr(rbac_service, "list_members", fake_list_members)
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When the members are listed
    response = client.get("/members")

    # Then the tenant members are returned
    assert response.status_code == 200
    assert response.json() == [
        {
            "membership_id": str(MEMBERSHIP_ID),
            "user_id": "22222222-2222-2222-2222-222222222222",
            "email": "member@example.com",
            "display_name": "Tenant Member",
            "membership_role": "member",
            "is_active": True,
            "role_ids": [],
        }
    ]


def test_list_members_denied_without_members_read() -> None:
    # Given a caller without members:read
    client = make_client(make_context(permissions=frozenset({"roles:read"})))

    # When the members are listed
    response = client.get("/members")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_assign_roles_allowed_with_members_manage(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:manage
    assigned: list[frozenset[uuid.UUID]] = []

    async def fake_assign_roles(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
        role_ids: Iterable[uuid.UUID],
    ) -> None:
        assert tenant_id == TENANT_ID
        assert membership_id == MEMBERSHIP_ID
        assigned.append(frozenset(role_ids))

    async def fake_list_members(_session: object, *, tenant_id: uuid.UUID) -> list[MemberView]:
        assert tenant_id == TENANT_ID
        return [make_member_view(role_ids=frozenset({ROLE_ID}))]

    monkeypatch.setattr(rbac_service, "assign_roles", fake_assign_roles)
    monkeypatch.setattr(rbac_service, "list_members", fake_list_members)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When roles are assigned to the member
    response = client.put(f"/members/{MEMBERSHIP_ID}/roles", json={"role_ids": [str(ROLE_ID)]})

    # Then the assignment is applied and returned
    assert response.status_code == 200
    assert response.json()["role_ids"] == [str(ROLE_ID)]
    assert assigned == [frozenset({ROLE_ID})]


def test_assign_roles_denied_without_members_manage() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When roles are assigned
    response = client.put(f"/members/{MEMBERSHIP_ID}/roles", json={"role_ids": []})

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_assign_roles_membership_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the membership in the caller's tenant
    async def fake_assign_roles(_session: object, **_kwargs: object) -> None:
        raise MembershipNotFoundError

    monkeypatch.setattr(rbac_service, "assign_roles", fake_assign_roles)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When roles are assigned to a missing or foreign membership
    response = client.put(f"/members/{uuid.uuid4()}/roles", json={"role_ids": []})

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "membership_not_found"}


def test_assign_roles_role_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the role in the caller's tenant
    async def fake_assign_roles(_session: object, **_kwargs: object) -> None:
        raise RoleNotFoundError

    monkeypatch.setattr(rbac_service, "assign_roles", fake_assign_roles)
    client = make_client(make_context(permissions=frozenset({"members:manage"})))

    # When a missing or foreign role is assigned
    response = client.put(f"/members/{MEMBERSHIP_ID}/roles", json={"role_ids": [str(ROLE_ID)]})

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "role_not_found"}


def test_rbac_endpoints_require_authentication() -> None:
    # Given an anonymous caller
    client = make_client(None)

    # When any RBAC endpoint is called
    responses = [
        client.get("/permissions"),
        client.get("/roles"),
        client.post("/roles", json={"name": "运营", "permissions": []}),
        client.get("/members"),
        client.put(f"/members/{MEMBERSHIP_ID}/roles", json={"role_ids": []}),
    ]

    # Then the caller is rejected
    for response in responses:
        assert response.status_code == 401
        assert response.json() == {"detail": "not_authenticated"}
