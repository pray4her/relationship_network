import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context, usage_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import USAGE_METRICS
from relationship_network_api.usage_service import (
    MetricBalance,
    SubscriptionNotFoundError,
    SubscriptionView,
    UsageSummaryView,
)

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


def make_summary() -> UsageSummaryView:
    now = datetime.now(UTC)
    trial_end = now + timedelta(days=14)
    return UsageSummaryView(
        subscription=SubscriptionView(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            plan_code="trial",
            plan_name="试用套餐",
            plan_version=1,
            status="trialing",
            started_at=now,
            trial_ends_at=trial_end,
            current_period_start=now,
            current_period_end=trial_end,
        ),
        metrics=tuple(
            MetricBalance(metric=metric, limit=1, used=0, reserved=0, remaining=1)
            for metric in USAGE_METRICS
        ),
    )


def stub_summary(monkeypatch: MonkeyPatch) -> None:
    async def fake_summary(_session: object, *, tenant_id: uuid.UUID) -> UsageSummaryView:
        assert tenant_id == TENANT_ID
        return make_summary()

    monkeypatch.setattr(usage_service, "get_usage_summary", fake_summary)


def test_billing_summary_returns_plan_and_metrics(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding billing:read and a trialing subscription
    stub_summary(monkeypatch)
    client = make_client(make_context(permissions=frozenset({"billing:read"})))

    # When the billing summary is requested
    response = client.get("/billing/summary")

    # Then the plan snapshot and all six metric balances are serialized in order
    assert response.status_code == 200
    body = cast("dict[str, object]", response.json())
    assert body["plan"] == {"code": "trial", "name": "试用套餐", "version": 1}
    assert body["status"] == "trialing"
    assert body["trial_ends_at"] is not None
    assert body["current_period_start"] is not None
    assert body["current_period_end"] is not None
    metrics = cast("list[dict[str, object]]", body["metrics"])
    assert [entry["metric"] for entry in metrics] == list(USAGE_METRICS)
    assert metrics[0] == {
        "metric": "owners",
        "limit": 1,
        "used": 0,
        "reserved": 0,
        "remaining": 1,
    }


def test_billing_summary_denied_without_billing_read() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When the billing summary is requested
    response = client.get("/billing/summary")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_billing_summary_requires_authentication() -> None:
    # Given an anonymous caller
    client = make_client(None)

    # When the billing summary is requested
    response = client.get("/billing/summary")

    # Then the caller is rejected
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_billing_summary_not_found_without_subscription(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding a current subscription
    async def fake_summary(_session: object, **_kwargs: object) -> UsageSummaryView:
        raise SubscriptionNotFoundError

    monkeypatch.setattr(usage_service, "get_usage_summary", fake_summary)
    client = make_client(make_context(permissions=frozenset({"billing:read"})))

    # When the billing summary is requested
    response = client.get("/billing/summary")

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "subscription_not_found"}
