import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Final, cast, final

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import order_service
from relationship_network_api.auth_service import Authentication, UserView
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_authentication,
    get_db_session,
    require_platform_admin,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import User
from relationship_network_api.order_service import (
    OrderNotFoundError,
    OrderStateError,
    OrderStatus,
    OrderView,
)

USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ORDER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SESSION_TTL_SECONDS: Final = 1209600
CREATED_AT: Final = datetime(2026, 1, 1, tzinfo=UTC)
REVIEWED_AT: Final = datetime(2026, 1, 2, tzinfo=UTC)
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


def make_authentication() -> Authentication:
    return Authentication(
        user=UserView(
            id=USER_ID,
            email="admin@example.com",
            display_name="平台管理员",
            is_platform_admin=True,
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


def make_order_view(*, status: OrderStatus = OrderStatus.PENDING) -> OrderView:
    reviewed = status != OrderStatus.PENDING
    return OrderView(
        id=ORDER_ID,
        tenant_id=TENANT_ID,
        plan_code="standard",
        plan_version=1,
        amount_cents=9900,
        payment_reference="bank-2026-0001",
        payment_channel="offline",
        payer_note="",
        status=status,
        idempotency_key="order-key-0001",
        submitted_by=uuid.uuid4(),
        reviewed_by=USER_ID if reviewed else None,
        reviewed_at=REVIEWED_AT if reviewed else None,
        review_note="凭证模糊" if status == OrderStatus.REJECTED else "",
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


def admin_client() -> TestClient:
    client = make_client(authentication=make_authentication(), bypass_guard=True)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")
    return client


def test_list_orders_returns_orders(monkeypatch: MonkeyPatch) -> None:
    # Given the service resolving orders for the supplied filters
    captured: dict[str, object] = {}

    async def fake_list(_session: object, **kwargs: object) -> list[OrderView]:
        captured.update(kwargs)
        return [make_order_view()]

    monkeypatch.setattr(order_service, "list_orders_admin", fake_list)
    client = admin_client()

    # When orders are listed with filters
    response = client.get(
        "/admin/orders",
        params={"status": "pending", "tenant_id": str(TENANT_ID)},
    )

    # Then the filters reach the service and the orders are returned
    assert response.status_code == 200
    orders = cast("list[dict[str, object]]", response.json()["orders"])
    assert len(orders) == 1
    assert orders[0]["id"] == str(ORDER_ID)
    assert orders[0]["status"] == "pending"
    assert captured["status"] == OrderStatus.PENDING
    assert captured["tenant_id"] == TENANT_ID


def test_list_orders_rejects_invalid_status_filter() -> None:
    # Given an authenticated platform admin
    client = admin_client()

    # When an unknown status filter is supplied
    response = client.get("/admin/orders", params={"status": "deleted"})

    # Then validation rejects it
    assert response.status_code == 422


def test_list_orders_requires_authentication() -> None:
    # Given an anonymous caller
    client = make_client(authentication=None)

    # When the order list is requested
    response = client.get("/admin/orders")

    # Then access is rejected as unauthenticated
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_list_orders_rejects_tenant_user() -> None:
    # Given an authenticated tenant user without platform admin rights
    client = make_client(
        authentication=make_authentication(),
        guard_user=make_user(is_platform_admin=False, mfa_enabled=True),
    )
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the order list is requested
    response = client.get("/admin/orders")

    # Then access is forbidden because tenant roles cannot derive admin rights
    assert response.status_code == 403
    assert response.json() == {"detail": "platform_admin_required"}


def test_confirm_order_returns_confirmed_view(monkeypatch: MonkeyPatch) -> None:
    # Given the service confirming the order under the admin's identity
    captured: dict[str, object] = {}

    async def fake_confirm(_session: object, **kwargs: object) -> OrderView:
        captured.update(kwargs)
        return make_order_view(status=OrderStatus.CONFIRMED)

    monkeypatch.setattr(order_service, "confirm_order", fake_confirm)
    client = admin_client()

    # When the order is confirmed twice
    first = client.post(f"/admin/orders/{ORDER_ID}/confirm")
    second = client.post(f"/admin/orders/{ORDER_ID}/confirm")

    # Then both calls succeed idempotently with the review attributed to the admin
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "confirmed"
    assert first.json()["reviewed_by"] == str(USER_ID)
    assert captured["order_id"] == ORDER_ID
    assert captured["reviewer_id"] == USER_ID


def test_confirm_order_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting an unknown order
    async def fake_confirm(_session: object, **_kwargs: object) -> OrderView:
        raise OrderNotFoundError

    monkeypatch.setattr(order_service, "confirm_order", fake_confirm)
    client = admin_client()

    # When the order is confirmed
    response = client.post(f"/admin/orders/{ORDER_ID}/confirm")

    # Then a uniform not-found is returned
    assert response.status_code == 404
    assert response.json() == {"detail": "order_not_found"}


def test_confirm_order_rejected_conflict(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting the order was already rejected
    async def fake_confirm(_session: object, **_kwargs: object) -> OrderView:
        raise OrderStateError

    monkeypatch.setattr(order_service, "confirm_order", fake_confirm)
    client = admin_client()

    # When the order is confirmed
    response = client.post(f"/admin/orders/{ORDER_ID}/confirm")

    # Then the state conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "order_already_rejected"}


def test_reject_order_returns_rejected_view(monkeypatch: MonkeyPatch) -> None:
    # Given the service rejecting the order with a reason
    captured: dict[str, object] = {}

    async def fake_reject(_session: object, **kwargs: object) -> OrderView:
        captured.update(kwargs)
        return make_order_view(status=OrderStatus.REJECTED)

    monkeypatch.setattr(order_service, "reject_order", fake_reject)
    client = admin_client()

    # When the order is rejected with a reason
    response = client.post(
        f"/admin/orders/{ORDER_ID}/reject",
        json={"reason": "凭证模糊"},
    )

    # Then the reason reaches the service and the rejected order is returned
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["review_note"] == "凭证模糊"
    assert captured["order_id"] == ORDER_ID
    assert captured["reviewer_id"] == USER_ID
    assert captured["reason"] == "凭证模糊"


def test_reject_order_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting an unknown order
    async def fake_reject(_session: object, **_kwargs: object) -> OrderView:
        raise OrderNotFoundError

    monkeypatch.setattr(order_service, "reject_order", fake_reject)
    client = admin_client()

    # When the order is rejected
    response = client.post(f"/admin/orders/{ORDER_ID}/reject", json={})

    # Then a uniform not-found is returned
    assert response.status_code == 404
    assert response.json() == {"detail": "order_not_found"}


def test_reject_order_confirmed_conflict(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting the order was already confirmed
    async def fake_reject(_session: object, **_kwargs: object) -> OrderView:
        raise OrderStateError

    monkeypatch.setattr(order_service, "reject_order", fake_reject)
    client = admin_client()

    # When the order is rejected
    response = client.post(f"/admin/orders/{ORDER_ID}/reject", json={})

    # Then the state conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "order_already_confirmed"}
