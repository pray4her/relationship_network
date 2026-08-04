import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from relationship_network_api import order_service, usage_service
from relationship_network_api.models import (
    OfflineOrder,
    PlatformAuditEvent,
    TenantSubscription,
    UsageLedgerEntry,
)
from relationship_network_api.order_service import OrderStateError, OrderView
from relationship_network_api.tenant_context import (
    set_platform_admin_context,
    set_tenant_context,
)

from .conftest import Stack, unique_email

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_tenant(stack: Stack, client: AsyncClient) -> tuple[uuid.UUID, uuid.UUID]:
    """Register a tenant through the API; returns (tenant_id, owner_user_id)."""
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "计费租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    body = cast("dict[str, dict[str, str]]", response.json())
    tenant_id = uuid.UUID(body["tenant"]["id"])
    user_id = uuid.UUID(body["user"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id, user_id


async def submit_order(client: AsyncClient, *, idempotency_key: str) -> dict[str, object]:
    """Submit a standard-plan offline order over the API; returns the body."""
    response = await client.post(
        "/billing/orders",
        json={
            "plan_code": "standard",
            "amount_cents": 9900,
            "payment_reference": f"bank-{idempotency_key}",
            "payer_note": "",
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 201
    return cast("dict[str, object]", response.json())


async def confirm(stack: Stack, order_id: uuid.UUID, reviewer_id: uuid.UUID) -> OrderView:
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        return await order_service.confirm_order(
            session,
            order_id=order_id,
            reviewer_id=reviewer_id,
        )


async def reject(
    stack: Stack,
    order_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    *,
    reason: str = "",
) -> OrderView:
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        return await order_service.reject_order(
            session,
            order_id=order_id,
            reviewer_id=reviewer_id,
            reason=reason,
        )


async def subscriptions_of(stack: Stack, tenant_id: uuid.UUID) -> list[TenantSubscription]:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        )
        return list(result.scalars())


async def audit_count(stack: Stack, *, action: str, target_id: str) -> int:
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        return (
            await session.execute(
                select(func.count())
                .select_from(PlatformAuditEvent)
                .where(
                    PlatformAuditEvent.action == action,
                    PlatformAuditEvent.target_id == target_id,
                )
            )
        ).scalar_one()


async def ledger_count(stack: Stack, tenant_id: uuid.UUID) -> int:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        return (
            await session.execute(select(func.count()).select_from(UsageLedgerEntry))
        ).scalar_one()


@pytest.mark.anyio
@pytest.mark.integration
async def test_confirm_activates_subscription_and_audits(stack: Stack, client: AsyncClient) -> None:
    # Given a trialing tenant with a submitted offline order
    tenant_id, owner_id = await register_tenant(stack, client)
    order = await submit_order(client, idempotency_key="confirm-flow-order")
    assert order["status"] == "pending"
    order_id = uuid.UUID(cast("str", order["id"]))

    # When a platform administrator confirms the order
    confirmed = await confirm(stack, order_id, owner_id)

    # Then the trial is cancelled and replaced by a one-month active subscription
    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == owner_id
    subscriptions = await subscriptions_of(stack, tenant_id)
    trial = next(row for row in subscriptions if row.status == "cancelled")
    assert trial.trial_ends_at is not None
    active = next(row for row in subscriptions if row.status == "active")
    assert active.offline_order_id == order_id
    period = active.current_period_end - active.current_period_start
    assert timedelta(days=27) < period < timedelta(days=32)

    # And the review is audited exactly once
    assert (
        await audit_count(
            stack,
            action=order_service.BILLING_ORDER_CONFIRM_ACTION,
            target_id=str(order_id),
        )
        == 1
    )


@pytest.mark.anyio
@pytest.mark.integration
async def test_submit_and_confirm_are_idempotent(stack: Stack, client: AsyncClient) -> None:
    # Given a trialing tenant
    tenant_id, owner_id = await register_tenant(stack, client)

    # When the same order is submitted twice under one idempotency key
    first = await submit_order(client, idempotency_key="repeat-order-key")
    second = await submit_order(client, idempotency_key="repeat-order-key")

    # Then both calls resolve to the same stored order
    assert first["id"] == second["id"]
    order_id = uuid.UUID(cast("str", first["id"]))
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        count = (await session.execute(select(func.count()).select_from(OfflineOrder))).scalar_one()
    assert count == 1

    # When the order is confirmed twice
    _ = await confirm(stack, order_id, owner_id)
    again = await confirm(stack, order_id, owner_id)

    # Then exactly one current subscription exists and the audit is not duplicated
    assert again.status == "confirmed"
    current = [
        row
        for row in await subscriptions_of(stack, tenant_id)
        if row.status in ("trialing", "active")
    ]
    assert len(current) == 1
    assert (
        await audit_count(
            stack,
            action=order_service.BILLING_ORDER_CONFIRM_ACTION,
            target_id=str(order_id),
        )
        == 1
    )


@pytest.mark.anyio
@pytest.mark.integration
async def test_reviewing_a_settled_order_conflicts(stack: Stack, client: AsyncClient) -> None:
    # Given one rejected order and one confirmed order
    tenant_id, owner_id = await register_tenant(stack, client)
    _ = tenant_id
    rejected = await submit_order(client, idempotency_key="reject-first-key")
    rejected_id = uuid.UUID(cast("str", rejected["id"]))
    view = await reject(stack, rejected_id, owner_id, reason="凭证模糊")
    assert view.status == "rejected"

    confirmed = await submit_order(client, idempotency_key="confirm-first-key")
    confirmed_id = uuid.UUID(cast("str", confirmed["id"]))
    _ = await confirm(stack, confirmed_id, owner_id)

    # When the opposite review lands on each
    # Then the state conflict is reported
    with pytest.raises(OrderStateError):
        _ = await confirm(stack, rejected_id, owner_id)
    with pytest.raises(OrderStateError):
        _ = await reject(stack, confirmed_id, owner_id)

    # And repeating the same review stays idempotent
    again = await reject(stack, rejected_id, owner_id)
    assert again.status == "rejected"


@pytest.mark.anyio
@pytest.mark.integration
async def test_cancel_expire_and_resubscribe(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant on a confirmed standard subscription with recorded usage
    tenant_id, owner_id = await register_tenant(stack, client)
    order = await submit_order(client, idempotency_key="first-period-key")
    order_id = uuid.UUID(cast("str", order["id"]))
    _ = await confirm(stack, order_id, owner_id)
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        _ = await usage_service.reserve(
            session,
            tenant_id=tenant_id,
            metric="searches",
            idempotency_key="usage-before-expiry",
        )
    ledger_before = await ledger_count(stack, tenant_id)
    assert ledger_before == 1

    # When the tenant cancels, the paid period keeps the tenant writable
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        cancelled = await usage_service.cancel_subscription(session, tenant_id=tenant_id)
    assert cancelled.cancel_requested_at is not None
    assert cancelled.status == "active"
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        assert await usage_service.is_tenant_writable(session, tenant_id=tenant_id)

    # When the sweeper runs past the period end
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        expired = await usage_service.expire_due_subscriptions(
            session,
            now=datetime.now(UTC) + timedelta(days=40),
        )

    # Then the subscription is expired and the tenant turns read-only
    assert expired >= 1
    subscriptions = await subscriptions_of(stack, tenant_id)
    assert {row.status for row in subscriptions} == {"cancelled", "expired"}
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        assert not await usage_service.is_tenant_writable(session, tenant_id=tenant_id)

    # When the tenant resubscribes with a new offline order
    renewal = await submit_order(client, idempotency_key="renewal-order-key")
    renewal_id = uuid.UUID(cast("str", renewal["id"]))
    renewed = await confirm(stack, renewal_id, owner_id)

    # Then the tenant is writable again and the usage ledger is untouched
    assert renewed.status == "confirmed"
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        assert await usage_service.is_tenant_writable(session, tenant_id=tenant_id)
    assert await ledger_count(stack, tenant_id) == ledger_before


@pytest.mark.anyio
@pytest.mark.integration
async def test_renewal_extends_the_paid_period(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with an active paid subscription
    tenant_id, owner_id = await register_tenant(stack, client)
    order = await submit_order(client, idempotency_key="renewal-base-key")
    order_id = uuid.UUID(cast("str", order["id"]))
    _ = await confirm(stack, order_id, owner_id)
    first = next(row for row in await subscriptions_of(stack, tenant_id) if row.status == "active")

    # When a second order is confirmed well before the paid period ends
    renewal = await submit_order(client, idempotency_key="renewal-extension-key")
    renewal_id = uuid.UUID(cast("str", renewal["id"]))
    _ = await confirm(stack, renewal_id, owner_id)

    # Then the new period anchors at the old period end, preserving prepaid time
    renewed = next(
        row
        for row in await subscriptions_of(stack, tenant_id)
        if row.offline_order_id == renewal_id
    )
    assert renewed.current_period_start == first.current_period_end
    assert renewed.current_period_end == usage_service.add_one_month(first.current_period_end)


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_and_admin_authorization(stack: Stack, client: AsyncClient) -> None:
    # Given tenant A with an offline order and tenant B without any
    tenant_a, _owner_a = await register_tenant(stack, client)
    order = await submit_order(client, idempotency_key="tenant-a-order-key")
    assert order["tenant_id"] == str(tenant_a)
    tenant_b, _owner_b = await register_tenant(stack, client)

    # When tenant B lists its orders over the API (the cookie now belongs to B)
    response = await client.get("/billing/orders")

    # Then tenant A's order is invisible
    assert response.status_code == 200
    assert response.json() == {"orders": []}

    # And the service-level listing under tenant B's context is empty as well
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        assert await order_service.list_tenant_orders(session, tenant_id=tenant_b) == []

    # When a plain tenant user probes the platform order review entry
    probe = await client.get("/admin/orders")

    # Then tenant roles cannot derive platform admin rights
    assert probe.status_code == 403
    assert probe.json() == {"detail": "platform_admin_required"}
