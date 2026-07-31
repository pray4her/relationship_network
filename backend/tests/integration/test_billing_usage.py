import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api import plan_service, usage_service
from relationship_network_api.config import load_database_settings
from relationship_network_api.models import (
    USAGE_METRICS,
    Plan,
    PlanEntitlement,
    PlanVersion,
    TenantSubscription,
    UsageLedgerEntry,
    UsageMetric,
)
from relationship_network_api.tenant_context import (
    set_platform_admin_context,
    set_tenant_context,
)
from relationship_network_api.usage_service import (
    IdempotencyKeyMismatchError,
    MetricBalance,
    QuotaExceededError,
    ReservationNotFoundError,
    ReservationStateError,
    ReservationView,
    SubscriptionInactiveError,
    UsageSummaryView,
)

from .conftest import Stack, unique_email

# Requires the local PostgreSQL container (127.0.0.1:15432) with `alembic upgrade head` applied.

TRIAL_LIMITS: Final[dict[str, int]] = {
    "owners": 1,
    "companies": 1,
    "active_jobs": 2,
    "searches": 20,
    "matches": 3,
    "reports": 1,
}


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_tenant(stack: Stack, client: AsyncClient) -> uuid.UUID:
    """Register a tenant through the API; returns the tenant id."""
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
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id


async def summary_of(stack: Stack, tenant_id: uuid.UUID) -> UsageSummaryView:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        return await usage_service.get_usage_summary(session, tenant_id=tenant_id)


def metric_of(summary: UsageSummaryView, metric: UsageMetric) -> MetricBalance:
    return next(balance for balance in summary.metrics if balance.metric == metric)


async def reserve(  # noqa: PLR0913
    stack: Stack,
    tenant_id: uuid.UUID,
    *,
    metric: UsageMetric,
    amount: int = 1,
    idempotency_key: str,
    ttl_seconds: int = 900,
) -> ReservationView:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        return await usage_service.reserve(
            session,
            tenant_id=tenant_id,
            metric=metric,
            amount=amount,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
        )


async def confirm(stack: Stack, tenant_id: uuid.UUID, reservation_id: uuid.UUID) -> ReservationView:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        return await usage_service.confirm(
            session,
            tenant_id=tenant_id,
            reservation_id=reservation_id,
        )


async def release(stack: Stack, tenant_id: uuid.UUID, reservation_id: uuid.UUID) -> ReservationView:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        return await usage_service.release(
            session,
            tenant_id=tenant_id,
            reservation_id=reservation_id,
        )


@pytest.mark.anyio
@pytest.mark.integration
async def test_registered_tenant_gets_trial_summary(stack: Stack, client: AsyncClient) -> None:
    # Given a freshly registered tenant
    before = datetime.now(UTC)
    _ = await register_tenant(stack, client)

    # When the billing summary is requested over the API
    response = await client.get("/billing/summary")

    # Then the trial plan snapshot with all six zeroed balances is returned
    assert response.status_code == 200
    body = cast("dict[str, object]", response.json())
    assert body["plan"] == {"code": "trial", "name": "试用套餐", "version": 1}
    assert body["status"] == "trialing"
    trial_ends_at = datetime.fromisoformat(cast("str", body["trial_ends_at"]))
    assert before + timedelta(days=13) < trial_ends_at < datetime.now(UTC) + timedelta(days=15)
    metrics = cast("list[dict[str, object]]", body["metrics"])
    assert [entry["metric"] for entry in metrics] == list(USAGE_METRICS)
    for entry in metrics:
        metric = cast("str", entry["metric"])
        assert entry["limit"] == TRIAL_LIMITS[metric]
        assert (entry["used"], entry["reserved"], entry["remaining"]) == (
            0,
            0,
            TRIAL_LIMITS[metric],
        )


@pytest.mark.anyio
@pytest.mark.integration
async def test_reserve_confirm_marks_usage(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with a trial subscription
    tenant_id = await register_tenant(stack, client)

    # When two searches are reserved and then confirmed
    reservation = await reserve(
        stack, tenant_id, metric="searches", amount=2, idempotency_key="confirm-flow"
    )
    assert reservation.status == "pending"
    pending_summary = await summary_of(stack, tenant_id)
    assert metric_of(pending_summary, "searches").reserved == 2
    confirmed = await confirm(stack, tenant_id, reservation.reservation_id)

    # Then the reservation is confirmed and the usage counts against the period
    assert confirmed.status == "confirmed"
    summary = await summary_of(stack, tenant_id)
    searches = metric_of(summary, "searches")
    assert (searches.used, searches.reserved, searches.remaining) == (2, 0, 18)


@pytest.mark.anyio
@pytest.mark.integration
async def test_reserve_release_frees_quota(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with a trial subscription
    tenant_id = await register_tenant(stack, client)

    # When a reservation is released instead of confirmed
    reservation = await reserve(
        stack, tenant_id, metric="matches", amount=1, idempotency_key="release-flow"
    )
    released = await release(stack, tenant_id, reservation.reservation_id)

    # Then the quota is fully available again
    assert released.status == "released"
    summary = await summary_of(stack, tenant_id)
    matches = metric_of(summary, "matches")
    assert (matches.used, matches.reserved, matches.remaining) == (0, 0, 3)


@pytest.mark.anyio
@pytest.mark.integration
async def test_reserve_is_idempotent_for_repeated_key(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with a trial subscription
    tenant_id = await register_tenant(stack, client)

    # When the same idempotency key is reserved twice
    first = await reserve(stack, tenant_id, metric="searches", idempotency_key="repeat-key")
    second = await reserve(stack, tenant_id, metric="searches", idempotency_key="repeat-key")

    # Then both calls resolve to the same reservation and a single ledger entry
    assert first.reservation_id == second.reservation_id
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        count = (
            await session.execute(
                select(func.count())
                .select_from(UsageLedgerEntry)
                .where(UsageLedgerEntry.idempotency_key == "repeat-key")
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_reserve_is_idempotent_under_concurrency(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with a trial subscription
    tenant_id = await register_tenant(stack, client)

    # When two concurrent reserves race on the same idempotency key
    first, second = await asyncio.gather(
        reserve(stack, tenant_id, metric="searches", idempotency_key="race-key"),
        reserve(stack, tenant_id, metric="searches", idempotency_key="race-key"),
    )

    # Then both calls resolve to the same reservation and a single ledger entry
    assert first.reservation_id == second.reservation_id
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        count = (
            await session.execute(
                select(func.count())
                .select_from(UsageLedgerEntry)
                .where(UsageLedgerEntry.idempotency_key == "race-key")
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_concurrent_reserves_never_overspend(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant whose trial plan allows exactly one owner
    tenant_id = await register_tenant(stack, client)

    # When two concurrent reserves compete for the last seat
    results = await asyncio.gather(
        reserve(stack, tenant_id, metric="owners", idempotency_key="seat-1"),
        reserve(stack, tenant_id, metric="owners", idempotency_key="seat-2"),
        return_exceptions=True,
    )

    # Then exactly one reserve succeeds and the other is rejected
    views = [result for result in results if isinstance(result, ReservationView)]
    rejections = [result for result in results if isinstance(result, QuotaExceededError)]
    assert len(views) == 1
    assert len(rejections) == 1
    summary = await summary_of(stack, tenant_id)
    owners = metric_of(summary, "owners")
    assert (owners.used, owners.reserved, owners.remaining) == (0, 1, 0)


@pytest.mark.anyio
@pytest.mark.integration
async def test_confirm_after_release_conflicts(stack: Stack, client: AsyncClient) -> None:
    # Given a released reservation
    tenant_id = await register_tenant(stack, client)
    reservation = await reserve(
        stack, tenant_id, metric="searches", idempotency_key="release-then-confirm"
    )
    released = await release(stack, tenant_id, reservation.reservation_id)
    assert released.status == "released"

    # When a confirm arrives late
    # Then the state conflict is reported
    with pytest.raises(ReservationStateError):
        _ = await confirm(stack, tenant_id, reservation.reservation_id)

    # And a repeated release stays idempotent
    again = await release(stack, tenant_id, reservation.reservation_id)
    assert again.status == "released"


@pytest.mark.anyio
@pytest.mark.integration
async def test_release_after_confirm_conflicts(stack: Stack, client: AsyncClient) -> None:
    # Given a confirmed reservation
    tenant_id = await register_tenant(stack, client)
    reservation = await reserve(
        stack, tenant_id, metric="searches", idempotency_key="confirm-then-release"
    )
    confirmed = await confirm(stack, tenant_id, reservation.reservation_id)
    assert confirmed.status == "confirmed"

    # When a release arrives late
    # Then the state conflict is reported
    with pytest.raises(ReservationStateError):
        _ = await release(stack, tenant_id, reservation.reservation_id)

    # And a repeated confirm stays idempotent
    again = await confirm(stack, tenant_id, reservation.reservation_id)
    assert again.status == "confirmed"


@pytest.mark.anyio
@pytest.mark.integration
async def test_confirm_unknown_reservation_is_not_found(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with a trial subscription
    tenant_id = await register_tenant(stack, client)

    # When an unknown reservation is confirmed
    # Then the miss is reported
    with pytest.raises(ReservationNotFoundError):
        _ = await confirm(stack, tenant_id, uuid.uuid4())


@pytest.mark.anyio
@pytest.mark.integration
async def test_expired_reservations_are_swept(stack: Stack, client: AsyncClient) -> None:
    # Given a reservation with a short TTL that has effectively expired
    tenant_id = await register_tenant(stack, client)
    _ = await reserve(
        stack,
        tenant_id,
        metric="searches",
        amount=5,
        idempotency_key="expiring",
        ttl_seconds=60,
    )
    pending_summary = await summary_of(stack, tenant_id)
    assert metric_of(pending_summary, "searches").reserved == 5

    # When the sweeper runs under the platform admin context past the expiry
    future = datetime.now(UTC) + timedelta(hours=1)
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        released = await usage_service.release_expired_reservations(session, now=future)

    # Then the expired reservation is released exactly once
    assert released == 1
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        rerun = await usage_service.release_expired_reservations(session, now=future)
    assert rerun == 0
    summary = await summary_of(stack, tenant_id)
    searches = metric_of(summary, "searches")
    assert (searches.used, searches.reserved, searches.remaining) == (0, 0, 20)


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_scopes_billing_rows_to_the_current_tenant(
    stack: Stack, client: AsyncClient
) -> None:
    # Given two tenants, where tenant A holds a subscription and ledger entries
    tenant_a = await register_tenant(stack, client)
    tenant_b = await register_tenant(stack, client)
    _ = await reserve(stack, tenant_a, metric="searches", idempotency_key="rls-a")

    # When tenant B queries the billing tables without any tenant filter
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        subscriptions = (await session.execute(select(TenantSubscription.id))).scalars().all()
        ledger = (await session.execute(select(UsageLedgerEntry.id))).all()

    # Then row level security hides tenant A's rows
    assert len(subscriptions) == 1
    assert ledger == []

    # When tenant A queries the same tables
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        subscriptions = (await session.execute(select(TenantSubscription.id))).scalars().all()
        ledger = (await session.execute(select(UsageLedgerEntry.id))).all()

    # Then only tenant A's rows are visible
    assert len(subscriptions) == 1
    assert len(ledger) == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_rls_blocks_cross_tenant_ledger_inserts(stack: Stack, client: AsyncClient) -> None:
    # Given two tenants that each own a subscription
    tenant_a = await register_tenant(stack, client)
    tenant_b = await register_tenant(stack, client)
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        subscription_a = (await session.execute(select(TenantSubscription.id))).scalar_one()
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        subscription_b = (await session.execute(select(TenantSubscription.id))).scalar_one()

    # When tenant A tries to write a ledger entry owned by tenant B
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        session.add(
            UsageLedgerEntry(
                id=uuid.uuid4(),
                tenant_id=tenant_b,
                subscription_id=subscription_b,
                reservation_id=uuid.uuid4(),
                metric="searches",
                amount=1,
                entry_type="reserve",
                idempotency_key="cross-a-to-b",
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

    # And tenant B tries to write a ledger entry owned by tenant A
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        session.add(
            UsageLedgerEntry(
                id=uuid.uuid4(),
                tenant_id=tenant_a,
                subscription_id=subscription_a,
                reservation_id=uuid.uuid4(),
                metric="searches",
                amount=1,
                entry_type="reserve",
                idempotency_key="cross-b-to-a",
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

    # Then no cross-tenant row landed
    async with stack.session_factory() as session:
        await set_platform_admin_context(session)
        count = (
            await session.execute(select(func.count()).select_from(UsageLedgerEntry))
        ).scalar_one()
    assert count == 0


@pytest.mark.anyio
@pytest.mark.integration
async def test_ledger_is_append_only_for_the_app_role(stack: Stack, client: AsyncClient) -> None:
    # Given a tenant with one ledger entry
    tenant_id = await register_tenant(stack, client)
    _ = await reserve(stack, tenant_id, metric="searches", idempotency_key="append-only")

    # When the app role tries to update or delete ledger rows
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        with pytest.raises(DBAPIError):
            _ = await session.execute(text("UPDATE usage_ledger_entries SET amount = 99"))
        await session.rollback()
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        with pytest.raises(DBAPIError):
            _ = await session.execute(text("DELETE FROM usage_ledger_entries"))
        await session.rollback()

    # Then the entry is untouched
    summary = await summary_of(stack, tenant_id)
    assert metric_of(summary, "searches").reserved == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_new_plan_version_keeps_existing_subscription_snapshot(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a tenant subscribed to the first published trial version
    tenant_id = await register_tenant(stack, client)

    # When a new version of the trial plan is published
    async with stack.session_factory() as session:
        plan_id = (await session.execute(select(Plan.id).where(Plan.code == "trial"))).scalar_one()
        version = await plan_service.publish_plan_version(
            session,
            plan_id=plan_id,
            entitlements=TRIAL_LIMITS,
        )
    try:
        # Then the new version is published
        assert version.version == 2

        # And the pre-existing subscription still resolves the version-1 snapshot
        summary = await summary_of(stack, tenant_id)
        assert summary.subscription.plan_version == 1
        assert {balance.metric: balance.limit for balance in summary.metrics} == TRIAL_LIMITS
    finally:
        # The app role may never delete plan rows, so the published version is
        # removed through a privileged connection to keep the catalog clean.
        await delete_plan_version(version.id)


async def delete_plan_version(plan_version_id: uuid.UUID) -> None:
    engine = create_async_engine(str(load_database_settings().database_url))
    try:
        async with engine.begin() as connection:
            _ = await connection.execute(
                delete(PlanEntitlement).where(PlanEntitlement.plan_version_id == plan_version_id)
            )
            _ = await connection.execute(
                delete(PlanVersion).where(PlanVersion.id == plan_version_id)
            )
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_expired_trial_blocks_reserves_but_reads_still_work(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a tenant whose trial period has ended
    tenant_id = await register_tenant(stack, client)
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        subscription = (
            await session.execute(
                select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
            )
        ).scalar_one()
        subscription.current_period_end = datetime.now(UTC) - timedelta(hours=1)
        await session.commit()

    # When a reserve is attempted
    # Then the inactive subscription is reported
    with pytest.raises(SubscriptionInactiveError):
        _ = await reserve(stack, tenant_id, metric="searches", idempotency_key="expired-trial")

    # And the read path still resolves the summary
    summary = await summary_of(stack, tenant_id)
    assert summary.subscription.status == "trialing"
    assert metric_of(summary, "searches").limit == TRIAL_LIMITS["searches"]


@pytest.mark.anyio
@pytest.mark.integration
async def test_reserve_rejects_idempotency_key_reuse_with_different_parameters(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a reservation stored under an idempotency key
    tenant_id = await register_tenant(stack, client)
    original = await reserve(
        stack, tenant_id, metric="searches", amount=1, idempotency_key="reused-key"
    )

    # When the same key is reused with a different amount or metric
    # Then the mismatch is rejected instead of silently returning the original
    with pytest.raises(IdempotencyKeyMismatchError):
        _ = await reserve(
            stack, tenant_id, metric="searches", amount=2, idempotency_key="reused-key"
        )
    with pytest.raises(IdempotencyKeyMismatchError):
        _ = await reserve(
            stack, tenant_id, metric="matches", amount=1, idempotency_key="reused-key"
        )

    # And an identical retry still returns the original reservation
    retry = await reserve(
        stack, tenant_id, metric="searches", amount=1, idempotency_key="reused-key"
    )
    assert retry.reservation_id == original.reservation_id


@pytest.mark.anyio
@pytest.mark.integration
async def test_settlement_stamps_the_reservations_own_subscription(
    stack: Stack, client: AsyncClient
) -> None:
    # Given a reservation taken on the tenant's trial subscription
    tenant_id = await register_tenant(stack, client)
    reservation = await reserve(
        stack, tenant_id, metric="searches", idempotency_key="stale-subscription"
    )

    # When the tenant rolls to a new subscription before settling
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        old_subscription = (
            await session.execute(
                select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
            )
        ).scalar_one()
        old_subscription.status = "expired"
        await session.flush()
        now = datetime.now(UTC)
        session.add(
            TenantSubscription(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                plan_version_id=old_subscription.plan_version_id,
                status="active",
                started_at=now,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        await session.commit()
    confirmed = await confirm(stack, tenant_id, reservation.reservation_id)

    # Then the confirm entry stays attributed to the original subscription
    assert confirmed.status == "confirmed"
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        confirm_row = (
            await session.execute(
                select(UsageLedgerEntry).where(
                    UsageLedgerEntry.reservation_id == reservation.reservation_id,
                    UsageLedgerEntry.entry_type == "confirm",
                )
            )
        ).scalar_one()
    assert confirm_row.subscription_id == old_subscription.id


@pytest.mark.anyio
@pytest.mark.integration
async def test_concurrent_sweeps_share_expired_reservations(
    stack: Stack, client: AsyncClient
) -> None:
    # Given an expired reservation
    tenant_id = await register_tenant(stack, client)
    _ = await reserve(
        stack,
        tenant_id,
        metric="searches",
        amount=5,
        idempotency_key="sweep-race",
        ttl_seconds=60,
    )
    future = datetime.now(UTC) + timedelta(hours=1)

    async def sweep() -> int:
        async with stack.session_factory() as session:
            await set_platform_admin_context(session)
            return await usage_service.release_expired_reservations(session, now=future)

    # When two sweepers race on the same expired reservation
    counts = await asyncio.gather(sweep(), sweep())

    # Then exactly one of them releases it and neither fails
    assert sum(counts) == 1
    summary = await summary_of(stack, tenant_id)
    assert metric_of(summary, "searches").reserved == 0
