import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import usage_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    WritableTenantDep,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def make_context() -> TenantContext:
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
        permissions=frozenset({"billing:manage"}),
    )


def make_client(monkeypatch: MonkeyPatch, *, writable: bool) -> TestClient:
    app = create_app(checks=())

    @app.get("/test/writable-probe")
    async def writable_probe(context: WritableTenantDep) -> dict[str, str]:
        return {"tenant_id": str(context.tenant_id)}

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    def override_context() -> TenantContext:
        return make_context()

    async def fake_writable(_session: object, *, tenant_id: uuid.UUID) -> bool:
        assert tenant_id == TENANT_ID
        return writable

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_tenant_context] = override_context
    monkeypatch.setattr(usage_service, "is_tenant_writable", fake_writable)
    return TestClient(app)


def test_writable_gate_admits_writable_tenant(monkeypatch: MonkeyPatch) -> None:
    # Given a tenant whose subscription is in period
    client = make_client(monkeypatch, writable=True)

    # When a gated write endpoint is requested
    response = client.get("/test/writable-probe")

    # Then the request passes the gate
    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(TENANT_ID)}


def test_writable_gate_rejects_read_only_tenant(monkeypatch: MonkeyPatch) -> None:
    # Given a tenant whose paid period has lapsed
    client = make_client(monkeypatch, writable=False)

    # When a gated write endpoint is requested
    response = client.get("/test/writable-probe")

    # Then the tenant is rejected as read-only
    assert response.status_code == 403
    assert response.json() == {"detail": "subscription_read_only"}
