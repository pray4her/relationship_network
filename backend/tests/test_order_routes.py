import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import order_service, tenant_context, usage_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.order_service import OrderStatus, OrderView
from relationship_network_api.plan_service import PlanNotFoundError
from relationship_network_api.usage_service import (
    IdempotencyKeyMismatchError,
    SubscriptionNotFoundError,
    SubscriptionView,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
ORDER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)

VALID_PAYLOAD = {
    "plan_code": "standard",
    "amount_cents": 9900,
    "payment_reference": "bank-2026-0001",
    "payer_note": "一季度费用",
    "idempotency_key": "order-key-0001",
}


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


def make_order_view(*, status: OrderStatus = OrderStatus.PENDING) -> OrderView:
    return OrderView(
        id=ORDER_ID,
        tenant_id=TENANT_ID,
        plan_code="standard",
        plan_version=1,
        amount_cents=9900,
        payment_reference="bank-2026-0001",
        payment_channel="offline",
        payer_note="一季度费用",
        status=status,
        idempotency_key="order-key-0001",
        submitted_by=USER_ID,
        reviewed_by=None,
        reviewed_at=None,
        review_note="",
        created_at=CREATED_AT,
    )


def make_subscription_view() -> SubscriptionView:
    now = datetime.now(UTC)
    return SubscriptionView(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        plan_code="standard",
        plan_name="标准版",
        plan_version=1,
        status="active",
        started_at=CREATED_AT,
        trial_ends_at=None,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_requested_at=now,
        offline_order_id=ORDER_ID,
    )


def stub_submit(monkeypatch: MonkeyPatch, captured: dict[str, object]) -> None:
    async def fake_submit(_session: object, **kwargs: object) -> OrderView:
        captured.update(kwargs)
        return make_order_view()

    monkeypatch.setattr(order_service, "submit_offline_order", fake_submit)


def test_submit_order_returns_created_view(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding billing:manage and a service accepting the order
    captured: dict[str, object] = {}
    stub_submit(monkeypatch, captured)
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When an offline order is submitted
    response = client.post("/billing/orders", json=VALID_PAYLOAD)

    # Then the pending order is returned and attributed to the tenant and caller
    assert response.status_code == 201
    assert response.json() == {
        "id": str(ORDER_ID),
        "tenant_id": str(TENANT_ID),
        "plan_code": "standard",
        "plan_version": 1,
        "amount_cents": 9900,
        "payment_reference": "bank-2026-0001",
        "payment_channel": "offline",
        "payer_note": "一季度费用",
        "status": "pending",
        "idempotency_key": "order-key-0001",
        "submitted_by": str(USER_ID),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": "",
        "created_at": "2026-01-01T00:00:00Z",
    }
    assert captured["tenant_id"] == TENANT_ID
    assert captured["user_id"] == USER_ID
    assert captured["plan_code"] == "standard"


def test_submit_order_rejects_invalid_payload() -> None:
    # Given a caller holding billing:manage
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When the idempotency key is too short
    response = client.post(
        "/billing/orders",
        json={**VALID_PAYLOAD, "idempotency_key": "short"},
    )

    # Then validation rejects the payload before reaching the service
    assert response.status_code == 422


def test_submit_order_requires_authentication() -> None:
    # Given an anonymous caller
    client = make_client(None)

    # When an offline order is submitted
    response = client.post("/billing/orders", json=VALID_PAYLOAD)

    # Then the caller is rejected
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_submit_order_denied_without_billing_manage() -> None:
    # Given a caller holding only billing:read
    client = make_client(make_context(permissions=frozenset({"billing:read"})))

    # When an offline order is submitted
    response = client.post("/billing/orders", json=VALID_PAYLOAD)

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_submit_order_plan_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the requested plan
    async def fake_submit(_session: object, **_kwargs: object) -> OrderView:
        raise PlanNotFoundError

    monkeypatch.setattr(order_service, "submit_offline_order", fake_submit)
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When an order is submitted for an unknown plan
    response = client.post(
        "/billing/orders",
        json={**VALID_PAYLOAD, "plan_code": "enterprise"},
    )

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "plan_not_found"}


def test_submit_order_idempotency_key_mismatch(monkeypatch: MonkeyPatch) -> None:
    # Given the service detecting an idempotency key reused with other parameters
    async def fake_submit(_session: object, **_kwargs: object) -> OrderView:
        raise IdempotencyKeyMismatchError

    monkeypatch.setattr(order_service, "submit_offline_order", fake_submit)
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When the order is submitted
    response = client.post("/billing/orders", json=VALID_PAYLOAD)

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "idempotency_key_mismatch"}


def test_list_orders_returns_orders(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding billing:read and a stored order
    async def fake_list(_session: object, *, tenant_id: uuid.UUID) -> list[OrderView]:
        assert tenant_id == TENANT_ID
        return [make_order_view(status=OrderStatus.CONFIRMED)]

    monkeypatch.setattr(order_service, "list_tenant_orders", fake_list)
    client = make_client(make_context(permissions=frozenset({"billing:read"})))

    # When the tenant's orders are requested
    response = client.get("/billing/orders")

    # Then the orders are returned
    assert response.status_code == 200
    orders = cast("list[dict[str, object]]", response.json()["orders"])
    assert len(orders) == 1
    assert orders[0]["id"] == str(ORDER_ID)
    assert orders[0]["status"] == "confirmed"


def test_list_orders_denied_without_billing_read() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When the tenant's orders are requested
    response = client.get("/billing/orders")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_cancel_subscription_returns_view(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding billing:manage and a current subscription
    async def fake_cancel(_session: object, *, tenant_id: uuid.UUID) -> SubscriptionView:
        assert tenant_id == TENANT_ID
        return make_subscription_view()

    monkeypatch.setattr(usage_service, "cancel_subscription", fake_cancel)
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When cancellation is requested
    response = client.post("/billing/subscription/cancel")

    # Then the flagged subscription is returned
    assert response.status_code == 200
    body = cast("dict[str, object]", response.json())
    assert body["tenant_id"] == str(TENANT_ID)
    assert body["plan_code"] == "standard"
    assert body["status"] == "active"
    assert body["cancel_requested_at"] is not None
    assert body["offline_order_id"] == str(ORDER_ID)


def test_cancel_subscription_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding a current subscription
    async def fake_cancel(_session: object, **_kwargs: object) -> SubscriptionView:
        raise SubscriptionNotFoundError

    monkeypatch.setattr(usage_service, "cancel_subscription", fake_cancel)
    client = make_client(make_context(permissions=frozenset({"billing:manage"})))

    # When cancellation is requested
    response = client.post("/billing/subscription/cancel")

    # Then the miss is reported
    assert response.status_code == 404
    assert response.json() == {"detail": "subscription_not_found"}


def test_cancel_subscription_denied_without_billing_manage() -> None:
    # Given a caller holding only billing:read
    client = make_client(make_context(permissions=frozenset({"billing:read"})))

    # When cancellation is requested
    response = client.post("/billing/subscription/cancel")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}
