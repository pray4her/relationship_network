import calendar
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal, cast, final

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import plan_service, tenant_context
from relationship_network_api.models import (
    CONCURRENT_METRICS,
    USAGE_METRICS,
    LedgerEntryType,
    SubscriptionStatus,
    TenantSubscription,
    UsageLedgerEntry,
    UsageMetric,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

DEFAULT_RESERVATION_TTL_SECONDS: Final = 900

SUBSCRIPTION_NOT_FOUND_DETAIL: Final = "subscription_not_found"
IDEMPOTENCY_KEY_MISMATCH_DETAIL: Final = "idempotency_key_mismatch"

_CURRENT_STATUSES: Final = ("trialing", "active")

ReservationStatus = Literal["pending", "confirmed", "released", "vacated"]
"""Settlement state of a reservation, derived from its ledger entries."""


@final
class SubscriptionNotFoundError(Exception):
    """Raised when the tenant has no current (trialing or active) subscription."""


@final
class SubscriptionInactiveError(Exception):
    """Raised when the current subscription is past its billing period end."""


@final
class UnknownMetricError(Exception):
    """Raised when a metric is not part of the usage metric catalog."""


@final
class QuotaExceededError(Exception):
    """Raised when a reservation would exceed the remaining quota."""


@final
class ReservationNotFoundError(Exception):
    """Raised when a reservation does not exist in the caller's tenant."""


@final
class ReservationStateError(Exception):
    """Raised when a reservation is already settled in a conflicting state."""


@final
class IdempotencyKeyMismatchError(Exception):
    """Raised when an idempotency key is reused with different request parameters."""


@final
@dataclass(frozen=True)
class SubscriptionView:
    """A tenant subscription with its pinned plan version."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_code: str
    plan_name: str
    plan_version: int
    status: SubscriptionStatus
    started_at: datetime
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    cancel_requested_at: datetime | None
    offline_order_id: uuid.UUID | None


@final
@dataclass(frozen=True)
class MetricBalance:
    """Quota accounting for one usage metric."""

    metric: UsageMetric
    limit: int
    used: int
    reserved: int
    remaining: int


@final
@dataclass(frozen=True)
class UsageSummaryView:
    """A tenant's subscription with per-metric balances in canonical order."""

    subscription: SubscriptionView
    metrics: tuple[MetricBalance, ...]


@final
@dataclass(frozen=True)
class ReservationView:
    """A reservation with its current settlement state."""

    reservation_id: uuid.UUID
    metric: UsageMetric
    amount: int
    status: ReservationStatus
    expires_at: datetime | None


@final
@dataclass(frozen=True)
class LedgerEntrySnapshot:
    """The balance-relevant facts of a ledger entry, detached from the ORM."""

    reservation_id: uuid.UUID
    subscription_id: uuid.UUID
    metric: UsageMetric
    entry_type: LedgerEntryType
    amount: int
    created_at: datetime
    expires_at: datetime | None


def compute_balance(
    metric: UsageMetric,
    limit: int,
    entries: Iterable[LedgerEntrySnapshot],
    period_start: datetime,
    now: datetime,
) -> MetricBalance:
    """Compute the balance of one metric from its ledger entries.

    Confirmed amounts count as used; open (unconfirmed, unreleased, unexpired)
    reservations count as reserved. Periodic metrics only count entries created
    within the current billing period; concurrent metrics count all entries.
    """
    if metric not in USAGE_METRICS:
        raise UnknownMetricError(metric)
    relevant = [
        entry
        for entry in entries
        if entry.metric == metric
        and (metric in CONCURRENT_METRICS or entry.created_at >= period_start)
    ]
    by_reservation: dict[uuid.UUID, list[LedgerEntrySnapshot]] = {}
    for entry in relevant:
        by_reservation.setdefault(entry.reservation_id, []).append(entry)
    used = 0
    reserved = 0
    for reservation_entries in by_reservation.values():
        settled = {entry.entry_type for entry in reservation_entries}
        if "vacate" in settled or "release" in settled:
            continue
        if "confirm" in settled:
            used += next(
                entry.amount for entry in reservation_entries if entry.entry_type == "confirm"
            )
        else:
            reserve = next(entry for entry in reservation_entries if entry.entry_type == "reserve")
            if reserve.expires_at is None or reserve.expires_at > now:
                reserved += reserve.amount
    return MetricBalance(
        metric=metric,
        limit=limit,
        used=used,
        reserved=reserved,
        remaining=limit - used - reserved,
    )


def add_one_month(dt: datetime) -> datetime:
    """Shift a datetime one calendar month forward, keeping its timezone.

    The day clamps to the target month's last day, so January 31 shifts to
    February 28 (or 29 on a leap year).
    """
    month_index = dt.year * 12 + dt.month  # 1-based months since year 0
    year, month = divmod(month_index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))


async def cancel_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> SubscriptionView:
    """Flag the tenant's current subscription for cancellation; idempotent.

    The subscription stays active until its current period end, when the
    expiry sweeper flips it to expired; cancelling only records the request.
    """
    resolved_now = now or datetime.now(UTC)
    subscription, version = await _load_current_subscription(session, tenant_id=tenant_id)
    if subscription.cancel_requested_at is not None:
        return _subscription_view(subscription, version)
    subscription.cancel_requested_at = resolved_now
    view = _subscription_view(subscription, version)
    await _commit(session)
    return view


async def expire_due_subscriptions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Expire every current subscription past its period end; returns the count.

    The caller must have set the platform admin context so row level security
    exposes subscriptions across all tenants.
    """
    resolved_now = now or datetime.now(UTC)
    result = await session.execute(
        update(TenantSubscription)
        .where(
            TenantSubscription.status.in_(_CURRENT_STATUSES),
            TenantSubscription.current_period_end <= resolved_now,
        )
        .values(status="expired")
    )
    await _commit(session)
    return cast("CursorResult[tuple[TenantSubscription]]", result).rowcount


async def is_tenant_writable(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    """Return whether the tenant may write, i.e. has a current subscription in period.

    A cancellation request does not revoke write access: the tenant keeps
    writing until the paid period actually ends.
    """
    resolved_now = now or datetime.now(UTC)
    result = await session.execute(
        select(TenantSubscription.id)
        .where(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status.in_(_CURRENT_STATUSES),
            TenantSubscription.current_period_end > resolved_now,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def start_trial_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> SubscriptionView:
    """Start the trial subscription for a new tenant; the caller owns the transaction."""
    resolved_now = now or datetime.now(UTC)
    version = await plan_service.get_latest_published_version(
        session,
        plan_code=plan_service.TRIAL_PLAN_CODE,
    )
    period_end = resolved_now + timedelta(days=plan_service.TRIAL_DURATION_DAYS)
    subscription = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_version_id=version.id,
        status="trialing",
        started_at=resolved_now,
        current_period_start=resolved_now,
        current_period_end=period_end,
        trial_ends_at=period_end,
    )
    session.add(subscription)
    return _subscription_view(subscription, version)


async def get_usage_summary(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> UsageSummaryView:
    """Return the tenant's subscription with per-metric balances.

    The immutable plan version pinned on the subscription IS the entitlement
    snapshot: later plan publications never change what this subscription sees.
    """
    resolved_now = now or datetime.now(UTC)
    subscription, version = await _load_current_subscription(session, tenant_id=tenant_id)
    entitlements = await plan_service.get_plan_entitlements(
        session,
        plan_version_id=subscription.plan_version_id,
    )
    entries = await _load_ledger_entries(session, subscription_id=subscription.id)
    return UsageSummaryView(
        subscription=_subscription_view(subscription, version),
        metrics=tuple(
            compute_balance(
                metric,
                entitlements[metric],
                entries,
                subscription.current_period_start,
                resolved_now,
            )
            for metric in USAGE_METRICS
        ),
    )


async def check_quota(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metric: UsageMetric,
    now: datetime | None = None,
) -> MetricBalance:
    """Read-only balance check for one metric; nothing is reserved or enforced."""
    _validate_metric(metric)
    resolved_now = now or datetime.now(UTC)
    subscription, _version = await _load_current_subscription(session, tenant_id=tenant_id)
    entitlements = await plan_service.get_plan_entitlements(
        session,
        plan_version_id=subscription.plan_version_id,
    )
    entries = await _load_ledger_entries(session, subscription_id=subscription.id)
    return compute_balance(
        metric,
        entitlements[metric],
        entries,
        subscription.current_period_start,
        resolved_now,
    )


async def reserve(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metric: UsageMetric,
    amount: int = 1,
    idempotency_key: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    ttl_seconds: int = DEFAULT_RESERVATION_TTL_SECONDS,
    now: datetime | None = None,
) -> ReservationView:
    """Reserve quota against a metric, idempotently per idempotency key.

    The subscription row is locked for the duration of the transaction so
    concurrent reserves of the same tenant serialize and never overspend.
    Periodic reservations expire after ttl_seconds; concurrent-metric
    reservations stay open until confirmed or released. Reusing an idempotency
    key with a different metric or amount raises IdempotencyKeyMismatchError.
    """
    _validate_metric(metric)
    resolved_now = now or datetime.now(UTC)
    subscription, _version = await _load_current_subscription(
        session,
        tenant_id=tenant_id,
        for_update=True,
    )
    if resolved_now > subscription.current_period_end:
        raise SubscriptionInactiveError
    existing = await _load_by_idempotency_key(
        session,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        _ensure_matching_request(existing, metric=metric, amount=amount)
        return await _reservation_view(
            session,
            tenant_id=tenant_id,
            reservation_id=existing.reservation_id,
        )
    entitlements = await plan_service.get_plan_entitlements(
        session,
        plan_version_id=subscription.plan_version_id,
    )
    entries = await _load_ledger_entries(session, subscription_id=subscription.id)
    balance = compute_balance(
        metric,
        entitlements[metric],
        entries,
        subscription.current_period_start,
        resolved_now,
    )
    if balance.remaining < amount:
        raise QuotaExceededError
    reservation_id = uuid.uuid4()
    expires_at = (
        resolved_now + timedelta(seconds=ttl_seconds) if metric not in CONCURRENT_METRICS else None
    )
    session.add(
        UsageLedgerEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            reservation_id=reservation_id,
            metric=metric,
            amount=amount,
            entry_type="reserve",
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            expires_at=expires_at,
        )
    )
    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        # A concurrent reserve with the same idempotency key won the race;
        # return its reservation instead of double-counting.
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        winner = await _load_by_idempotency_key(
            session,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )
        if winner is None:
            raise
        _ensure_matching_request(winner, metric=metric, amount=amount)
        return await _reservation_view(
            session,
            tenant_id=tenant_id,
            reservation_id=winner.reservation_id,
        )
    except SQLAlchemyError:
        await session.rollback()
        raise
    return ReservationView(
        reservation_id=reservation_id,
        metric=metric,
        amount=amount,
        status="pending",
        expires_at=expires_at,
    )


async def confirm(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> ReservationView:
    """Settle a reservation as consumed usage; idempotent per reservation."""
    return await _settle(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
        entry_type="confirm",
        conflict_type="release",
        status="confirmed",
    )


async def release(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> ReservationView:
    """Settle a reservation as freed quota; idempotent per reservation."""
    return await _settle(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
        entry_type="release",
        conflict_type="confirm",
        status="released",
    )


async def vacate_confirmed(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> ReservationView:
    """Free a confirmed concurrent seat; idempotent per reservation.

    Vacate applies only after confirm. It conflicts with release (pending
    reservations must use release instead) and with a missing confirm.
    """
    _ = await _load_current_subscription(session, tenant_id=tenant_id, for_update=True)
    entries = await _load_reservation_entries(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
    )
    reserve_entry = _reserve_entry(entries)
    if _has_entry(entries, "vacate"):
        return ReservationView(
            reservation_id=reservation_id,
            metric=reserve_entry.metric,
            amount=reserve_entry.amount,
            status="vacated",
            expires_at=reserve_entry.expires_at,
        )
    if _has_entry(entries, "release"):
        raise ReservationStateError
    if not _has_entry(entries, "confirm"):
        raise ReservationStateError
    session.add(
        _settlement_entry(
            tenant_id=tenant_id,
            reserve_entry=reserve_entry,
            entry_type="vacate",
        )
    )
    await _commit(session)
    return ReservationView(
        reservation_id=reservation_id,
        metric=reserve_entry.metric,
        amount=reserve_entry.amount,
        status="vacated",
        expires_at=reserve_entry.expires_at,
    )


async def _settle(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    entry_type: LedgerEntryType,
    conflict_type: LedgerEntryType,
    status: ReservationStatus,
) -> ReservationView:
    """Append the settlement entry for a reservation, mirroring confirm/release.

    The settlement entry is stamped with the reservation's own subscription so
    settling after a subscription change stays attributed to the original
    period. Repeating the same settlement returns the current view; settling
    with the conflicting type raises ReservationStateError.
    """
    _ = await _load_current_subscription(session, tenant_id=tenant_id, for_update=True)
    entries = await _load_reservation_entries(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
    )
    reserve_entry = _reserve_entry(entries)
    if _has_entry(entries, entry_type):
        return _view_from_entries(reservation_id, entries)
    if _has_entry(entries, conflict_type):
        raise ReservationStateError
    session.add(
        _settlement_entry(
            tenant_id=tenant_id,
            reserve_entry=reserve_entry,
            entry_type=entry_type,
        )
    )
    await _commit(session)
    return ReservationView(
        reservation_id=reservation_id,
        metric=reserve_entry.metric,
        amount=reserve_entry.amount,
        status=status,
        expires_at=reserve_entry.expires_at,
    )


async def release_expired_reservations(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Release every expired open reservation; returns the number released.

    The caller must have set the platform admin context so row level security
    exposes reservations across all tenants. Each release is inserted in a
    savepoint: when a concurrent sweeper settles the same reservation first,
    the unique violation skips that reservation instead of failing the run.
    """
    resolved_now = now or datetime.now(UTC)
    settled = (
        select(UsageLedgerEntry.reservation_id)
        .where(UsageLedgerEntry.entry_type.in_(("confirm", "release")))
        .scalar_subquery()
    )
    result = await session.execute(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.entry_type == "reserve",
            UsageLedgerEntry.expires_at.is_not(None),
            UsageLedgerEntry.expires_at <= resolved_now,
            UsageLedgerEntry.reservation_id.not_in(settled),
        )
    )
    expired = result.scalars().all()
    released = 0
    for entry in expired:
        try:
            async with session.begin_nested():
                session.add(
                    UsageLedgerEntry(
                        id=uuid.uuid4(),
                        tenant_id=entry.tenant_id,
                        subscription_id=entry.subscription_id,
                        reservation_id=entry.reservation_id,
                        metric=entry.metric,
                        amount=entry.amount,
                        entry_type="release",
                        idempotency_key=f"{entry.reservation_id}:release",
                    )
                )
        except IntegrityError:
            # A concurrent sweeper released this reservation first.
            continue
        released += 1
    await _commit(session)
    return released


def _validate_metric(metric: UsageMetric) -> None:
    if metric not in USAGE_METRICS:
        raise UnknownMetricError(metric)


async def _load_current_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    for_update: bool = False,
) -> tuple[TenantSubscription, plan_service.PlanVersionView]:
    statement = (
        select(TenantSubscription)
        .where(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status.in_(_CURRENT_STATUSES),
        )
        .order_by(TenantSubscription.started_at.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    subscription = (await session.execute(statement)).scalar_one_or_none()
    if subscription is None:
        raise SubscriptionNotFoundError
    version = await plan_service.get_plan_version(
        session,
        plan_version_id=subscription.plan_version_id,
    )
    return subscription, version


def _ensure_matching_request(
    entry: UsageLedgerEntry,
    *,
    metric: UsageMetric,
    amount: int,
) -> None:
    """Reject an idempotency key reused with different request parameters."""
    if entry.metric != metric or entry.amount != amount:
        raise IdempotencyKeyMismatchError


async def _load_ledger_entries(
    session: AsyncSession,
    *,
    subscription_id: uuid.UUID,
) -> list[LedgerEntrySnapshot]:
    result = await session.execute(
        select(UsageLedgerEntry).where(UsageLedgerEntry.subscription_id == subscription_id)
    )
    return [_snapshot(entry) for entry in result.scalars()]


async def _load_reservation_entries(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> list[LedgerEntrySnapshot]:
    result = await session.execute(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.tenant_id == tenant_id,
            UsageLedgerEntry.reservation_id == reservation_id,
        )
    )
    return [_snapshot(entry) for entry in result.scalars()]


async def _load_by_idempotency_key(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    idempotency_key: str,
) -> UsageLedgerEntry | None:
    result = await session.execute(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.tenant_id == tenant_id,
            UsageLedgerEntry.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _reservation_view(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> ReservationView:
    entries = await _load_reservation_entries(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
    )
    return _view_from_entries(reservation_id, entries)


def _reserve_entry(entries: list[LedgerEntrySnapshot]) -> LedgerEntrySnapshot:
    reserve_entry = next(
        (entry for entry in entries if entry.entry_type == "reserve"),
        None,
    )
    if reserve_entry is None:
        raise ReservationNotFoundError
    return reserve_entry


def _has_entry(entries: list[LedgerEntrySnapshot], entry_type: LedgerEntryType) -> bool:
    return any(entry.entry_type == entry_type for entry in entries)


def _view_from_entries(
    reservation_id: uuid.UUID,
    entries: list[LedgerEntrySnapshot],
) -> ReservationView:
    reserve_entry = _reserve_entry(entries)
    status: ReservationStatus
    if _has_entry(entries, "vacate"):
        status = "vacated"
    elif _has_entry(entries, "confirm"):
        status = "confirmed"
    elif _has_entry(entries, "release"):
        status = "released"
    else:
        status = "pending"
    return ReservationView(
        reservation_id=reservation_id,
        metric=reserve_entry.metric,
        amount=reserve_entry.amount,
        status=status,
        expires_at=reserve_entry.expires_at,
    )


def _settlement_entry(
    *,
    tenant_id: uuid.UUID,
    reserve_entry: LedgerEntrySnapshot,
    entry_type: LedgerEntryType,
) -> UsageLedgerEntry:
    return UsageLedgerEntry(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        subscription_id=reserve_entry.subscription_id,
        reservation_id=reserve_entry.reservation_id,
        metric=reserve_entry.metric,
        amount=reserve_entry.amount,
        entry_type=entry_type,
        idempotency_key=f"{reserve_entry.reservation_id}:{entry_type}",
    )


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise


def _snapshot(entry: UsageLedgerEntry) -> LedgerEntrySnapshot:
    return LedgerEntrySnapshot(
        reservation_id=entry.reservation_id,
        subscription_id=entry.subscription_id,
        metric=entry.metric,
        entry_type=entry.entry_type,
        amount=entry.amount,
        created_at=entry.created_at,
        expires_at=entry.expires_at,
    )


def _subscription_view(
    subscription: TenantSubscription,
    version: plan_service.PlanVersionView,
) -> SubscriptionView:
    return SubscriptionView(
        id=subscription.id,
        tenant_id=subscription.tenant_id,
        plan_code=version.plan_code,
        plan_name=version.plan_name,
        plan_version=version.version,
        status=subscription.status,
        started_at=subscription.started_at,
        trial_ends_at=subscription.trial_ends_at,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_requested_at=subscription.cancel_requested_at,
        offline_order_id=subscription.offline_order_id,
    )
