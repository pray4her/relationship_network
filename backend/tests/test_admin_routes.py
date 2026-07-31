import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Final, cast, final

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import admin_service, audit_service
from relationship_network_api.admin_service import (
    TenantDetailView,
    TenantNotFoundError,
    TenantSummaryView,
)
from relationship_network_api.audit_service import AuditEventView
from relationship_network_api.auth_service import Authentication, UserView
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_authentication,
    get_db_session,
    require_platform_admin,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import TenantStatus, User

USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SESSION_TTL_SECONDS: Final = 1209600
CREATED_AT: Final = datetime(2026, 1, 1, tzinfo=UTC)
UNSET: Final = object()


@final
class ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


@final
class FakeSession:
    """Serves the single user lookup performed by require_platform_admin."""

    def __init__(self, user: User | None) -> None:
        self._user = user

    async def execute(self, _statement: object) -> ScalarResult:
        return ScalarResult(self._user)


def make_authentication(*, is_platform_admin: bool = True) -> Authentication:
    return Authentication(
        user=UserView(
            id=USER_ID,
            email="admin@example.com",
            display_name="平台管理员",
            is_platform_admin=is_platform_admin,
        ),
        membership=None,
        expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS),
        renewed=False,
    )


def make_user(*, is_platform_admin: bool, mfa_enabled: bool) -> User:
    return User(
        id=USER_ID,
        email="admin@example.com",
        display_name="平台管理员",
        password_hash="hash",
        is_active=True,
        is_platform_admin=is_platform_admin,
        totp_enabled_at=datetime.now(UTC) if mfa_enabled else None,
    )


def make_summary() -> TenantSummaryView:
    return TenantSummaryView(
        id=TENANT_ID,
        name="Acme 科技",
        slug="acme-1234abcd",
        status="active",
        member_count=2,
        created_at=CREATED_AT,
    )


def make_detail(
    *,
    status: TenantStatus = "active",
    mfa_required: bool = False,
) -> TenantDetailView:
    return TenantDetailView(
        id=TENANT_ID,
        name="Acme 科技",
        slug="acme-1234abcd",
        status=status,
        mfa_required=mfa_required,
        member_count=2,
        created_at=CREATED_AT,
    )


def make_client(
    *,
    authentication: Authentication | None,
    guard_user: User | None | object = UNSET,
    bypass_guard: bool = False,
) -> TestClient:
    app = create_app(checks=())

    def override_authentication() -> Authentication | None:
        return authentication

    async def override_session() -> AsyncIterator[AsyncSession]:
        resolved = cast("User | None", None if guard_user is UNSET else guard_user)
        yield cast("AsyncSession", cast("object", FakeSession(resolved)))

    app.dependency_overrides[get_authentication] = override_authentication
    app.dependency_overrides[get_db_session] = override_session
    if bypass_guard:

        async def override_guard() -> Authentication:
            assert authentication is not None
            return authentication

        app.dependency_overrides[require_platform_admin] = override_guard
    return TestClient(app)


def test_admin_routes_require_authentication() -> None:
    # Given an anonymous caller
    client = make_client(authentication=None)

    # When a platform endpoint is requested
    response = client.get("/admin/tenants")

    # Then access is rejected as unauthenticated
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_admin_routes_reject_tenant_user() -> None:
    # Given an authenticated tenant user without platform admin rights
    client = make_client(
        authentication=make_authentication(is_platform_admin=False),
        guard_user=make_user(is_platform_admin=False, mfa_enabled=True),
    )
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When a platform endpoint is requested
    response = client.get("/admin/tenants")

    # Then access is forbidden because tenant roles cannot derive admin rights
    assert response.status_code == 403
    assert response.json() == {"detail": "platform_admin_required"}


def test_admin_routes_reject_admin_without_mfa() -> None:
    # Given a platform administrator who has not enrolled MFA
    client = make_client(
        authentication=make_authentication(),
        guard_user=make_user(is_platform_admin=True, mfa_enabled=False),
    )
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When a platform endpoint is requested
    response = client.get("/admin/tenants")

    # Then the management entry stays closed until MFA is enrolled
    assert response.status_code == 403
    assert response.json() == {"detail": "mfa_required"}


def test_admin_routes_admit_admin_with_mfa(monkeypatch: MonkeyPatch) -> None:
    # Given a platform administrator with MFA enrolled
    async def fake_search(
        _session: object,
        **_kwargs: object,
    ) -> tuple[list[TenantSummaryView], int]:
        return [make_summary()], 1

    monkeypatch.setattr(admin_service, "search_tenants", fake_search)
    client = make_client(
        authentication=make_authentication(),
        guard_user=make_user(is_platform_admin=True, mfa_enabled=True),
    )
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the tenant list is requested
    response = client.get("/admin/tenants")

    # Then the tenant summaries are returned
    assert response.status_code == 200
    assert response.json() == {
        "tenants": [
            {
                "id": str(TENANT_ID),
                "name": "Acme 科技",
                "slug": "acme-1234abcd",
                "status": "active",
                "member_count": 2,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
        "total": 1,
    }


def test_search_tenants_passes_filters(monkeypatch: MonkeyPatch) -> None:
    # Given a search endpoint backed by the admin service
    captured: dict[str, object] = {}

    async def fake_search(
        _session: object,
        **kwargs: object,
    ) -> tuple[list[TenantSummaryView], int]:
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr(admin_service, "search_tenants", fake_search)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When filters are supplied
    response = client.get("/admin/tenants", params={"query": "acme", "status": "suspended"})

    # Then they reach the service
    assert response.status_code == 200
    assert captured["query"] == "acme"
    assert captured["status"] == "suspended"


def test_search_tenants_rejects_invalid_status_filter() -> None:
    # Given an authenticated platform admin
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When an unknown status filter is supplied
    response = client.get("/admin/tenants", params={"status": "deleted"})

    # Then validation rejects it
    assert response.status_code == 422


def test_read_tenant_returns_detail(monkeypatch: MonkeyPatch) -> None:
    # Given the service resolving a tenant
    async def fake_detail(_session: object, *, tenant_id: uuid.UUID) -> TenantDetailView:
        assert tenant_id == TENANT_ID
        return make_detail(mfa_required=True)

    monkeypatch.setattr(admin_service, "get_tenant_detail", fake_detail)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When the tenant detail is requested
    response = client.get(f"/admin/tenants/{TENANT_ID}")

    # Then the overview is returned
    assert response.status_code == 200
    assert response.json() == {
        "id": str(TENANT_ID),
        "name": "Acme 科技",
        "slug": "acme-1234abcd",
        "status": "active",
        "mfa_required": True,
        "member_count": 2,
        "created_at": "2026-01-01T00:00:00Z",
    }


def test_read_tenant_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting an unknown tenant
    async def fake_detail(_session: object, **_kwargs: object) -> TenantDetailView:
        raise TenantNotFoundError

    monkeypatch.setattr(admin_service, "get_tenant_detail", fake_detail)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When the tenant detail is requested
    response = client.get(f"/admin/tenants/{TENANT_ID}")

    # Then a uniform not-found is returned
    assert response.status_code == 404
    assert response.json() == {"detail": "tenant_not_found"}


def test_update_tenant_status_applies_change(monkeypatch: MonkeyPatch) -> None:
    # Given the service applying a status change
    captured: dict[str, object] = {}

    async def fake_update(_session: object, **kwargs: object) -> TenantDetailView:
        captured.update(kwargs)
        return make_detail(status="suspended")

    monkeypatch.setattr(admin_service, "update_tenant_status", fake_update)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When the tenant is suspended
    response = client.post(
        f"/admin/tenants/{TENANT_ID}/status",
        json={"status": "suspended"},
    )

    # Then the change is attributed to the admin and returned
    assert response.status_code == 200
    assert response.json()["status"] == "suspended"
    assert captured["tenant_id"] == TENANT_ID
    assert captured["status"] == "suspended"
    assert captured["actor_id"] == USER_ID


def test_update_tenant_status_rejects_invalid_status() -> None:
    # Given an authenticated platform admin
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When an unknown status is submitted
    response = client.post(
        f"/admin/tenants/{TENANT_ID}/status",
        json={"status": "deleted"},
    )

    # Then validation rejects it
    assert response.status_code == 422


def test_update_tenant_status_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting an unknown tenant
    async def fake_update(_session: object, **_kwargs: object) -> TenantDetailView:
        raise TenantNotFoundError

    monkeypatch.setattr(admin_service, "update_tenant_status", fake_update)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When the status change is submitted
    response = client.post(
        f"/admin/tenants/{TENANT_ID}/status",
        json={"status": "suspended"},
    )

    # Then a uniform not-found is returned
    assert response.status_code == 404
    assert response.json() == {"detail": "tenant_not_found"}


def test_audit_events_are_listed(monkeypatch: MonkeyPatch) -> None:
    # Given recorded audit events
    event = AuditEventView(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        actor_id=USER_ID,
        action="tenant.status_update",
        target_type="tenant",
        target_id=str(TENANT_ID),
        result="success",
        detail="status=suspended",
        created_at=CREATED_AT,
    )

    async def fake_list(_session: object, **_kwargs: object) -> list[AuditEventView]:
        return [event]

    monkeypatch.setattr(audit_service, "list_events", fake_list)
    client = make_client(authentication=make_authentication(), bypass_guard=True)

    # When the audit trail is requested
    response = client.get("/admin/audit-events")

    # Then the recorded operations are returned
    assert response.status_code == 200
    assert response.json() == {
        "events": [
            {
                "id": "44444444-4444-4444-4444-444444444444",
                "actor_id": str(USER_ID),
                "action": "tenant.status_update",
                "target_type": "tenant",
                "target_id": str(TENANT_ID),
                "result": "success",
                "detail": "status=suspended",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
    }


def test_audit_events_require_platform_admin() -> None:
    # Given an authenticated tenant user without platform admin rights
    client = make_client(
        authentication=make_authentication(is_platform_admin=False),
        guard_user=make_user(is_platform_admin=False, mfa_enabled=True),
    )
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the audit trail is requested
    response = client.get("/admin/audit-events")

    # Then access is forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "platform_admin_required"}
