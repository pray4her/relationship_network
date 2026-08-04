"""Route-level tests for /companies endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import company_service, tenant_audit_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.company_service import (
    CompanyArchivedError,
    CompanyNotFoundError,
    CompanyView,
)
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import CompanyStatus
from relationship_network_api.routers.companies import require_companies_manage
from relationship_network_api.usage_service import QuotaExceededError

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
COMPANY_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=UTC)


def make_context(*, permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="owner",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(
                id=USER_ID,
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


def make_company_view(*, status: CompanyStatus = "active") -> CompanyView:
    return CompanyView(
        id=COMPANY_ID,
        tenant_id=TENANT_ID,
        name="示例企业",
        profile_text="简介",
        status=status,
        usage_reservation_id=uuid.uuid4(),
        created_at=NOW,
        updated_at=NOW,
        archived_at=NOW if status == "archived" else None,
    )


def make_client(context: TenantContext | None, *, writable: bool = True) -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_db_session] = override_session
    if context is None:

        def override_authentication() -> None:
            return None

        app.dependency_overrides[get_authentication] = override_authentication
    else:

        async def override_tenant_context() -> TenantContext:
            return context

        app.dependency_overrides[get_tenant_context] = override_tenant_context

        async def override_writable() -> TenantContext:
            if "companies:manage" not in context.permissions:
                from fastapi import HTTPException, status as http_status

                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="permission_denied",
                )
            if not writable:
                from fastapi import HTTPException, status as http_status

                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="subscription_read_only",
                )
            return context

        app.dependency_overrides[require_companies_manage] = override_writable

    return TestClient(app)


def test_create_company_requires_manage_permission(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:read"})))

    async def fail_create(*_args: object, **_kwargs: object) -> CompanyView:
        raise AssertionError("create should not run")

    monkeypatch.setattr(company_service, "create_company", fail_create)
    response = client.post("/companies", json={"name": "A"})
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_create_company_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:manage"})))

    async def fake_create(*_args: object, **_kwargs: object) -> CompanyView:
        return make_company_view()

    monkeypatch.setattr(company_service, "create_company", fake_create)
    response = client.post("/companies", json={"name": "示例企业", "profile_text": "简介"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(COMPANY_ID)
    assert body["name"] == "示例企业"
    assert body["status"] == "active"


def test_create_company_maps_quota_exceeded(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:manage"})))

    async def exceed(*_args: object, **_kwargs: object) -> CompanyView:
        raise QuotaExceededError

    monkeypatch.setattr(company_service, "create_company", exceed)
    response = client.post("/companies", json={"name": "超额企业"})
    assert response.status_code == 409
    assert response.json() == {"detail": "company_quota_exceeded"}


def test_create_company_rejects_read_only_subscription(monkeypatch: MonkeyPatch) -> None:
    client = make_client(
        make_context(permissions=frozenset({"companies:manage"})),
        writable=False,
    )

    async def fail_create(*_args: object, **_kwargs: object) -> CompanyView:
        raise AssertionError("create should not run")

    monkeypatch.setattr(company_service, "create_company", fail_create)
    response = client.post("/companies", json={"name": "只读"})
    assert response.status_code == 403
    assert response.json() == {"detail": "subscription_read_only"}


def test_get_company_not_found(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:read"})))

    async def missing(*_args: object, **_kwargs: object) -> CompanyView:
        raise CompanyNotFoundError

    monkeypatch.setattr(company_service, "get_company", missing)
    response = client.get(f"/companies/{COMPANY_ID}")
    assert response.status_code == 404
    assert response.json() == {"detail": "company_not_found"}


def test_update_archived_company_conflict(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:manage"})))

    async def archived(*_args: object, **_kwargs: object) -> CompanyView:
        raise CompanyArchivedError

    monkeypatch.setattr(company_service, "update_company", archived)
    response = client.patch(f"/companies/{COMPANY_ID}", json={"name": "新名称"})
    assert response.status_code == 409
    assert response.json() == {"detail": "company_archived"}


def test_archive_company_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:manage"})))

    async def fake_archive(*_args: object, **_kwargs: object) -> CompanyView:
        return make_company_view(status="archived")

    monkeypatch.setattr(company_service, "archive_company", fake_archive)
    response = client.post(f"/companies/{COMPANY_ID}/archive")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_list_events_requires_read(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"companies:manage"})))

    async def fake_get(*_args: object, **_kwargs: object) -> CompanyView:
        return make_company_view()

    async def fake_events(*_args: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(company_service, "get_company", fake_get)
    monkeypatch.setattr(tenant_audit_service, "list_events_for_target", fake_events)
    response = client.get(f"/companies/{COMPANY_ID}/events")
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_anonymous_create_rejected() -> None:
    client = make_client(None)
    response = client.post("/companies", json={"name": "匿名"})
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}
