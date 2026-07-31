import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from relationship_network_api.models import USAGE_METRICS, LedgerEntryType, UsageMetric
from relationship_network_api.usage_service import (
    LedgerEntrySnapshot,
    UnknownMetricError,
    compute_balance,
)

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
PERIOD_START = NOW - timedelta(days=7)


def pending(
    amount: int,
    *,
    metric: UsageMetric = "searches",
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> list[LedgerEntrySnapshot]:
    """A lone reserve entry: an open reservation."""
    return [
        LedgerEntrySnapshot(
            reservation_id=uuid.uuid4(),
            subscription_id=uuid.uuid4(),
            metric=metric,
            entry_type="reserve",
            amount=amount,
            created_at=created_at if created_at is not None else NOW - timedelta(hours=1),
            expires_at=expires_at,
        )
    ]


def settled(
    entry_type: str,
    amount: int,
    *,
    metric: UsageMetric = "searches",
    created_at: datetime | None = None,
) -> list[LedgerEntrySnapshot]:
    """A reserve entry plus its confirm/release counterpart sharing the reservation id."""
    reservation_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    created = created_at if created_at is not None else NOW - timedelta(hours=1)
    return [
        LedgerEntrySnapshot(
            reservation_id=reservation_id,
            subscription_id=subscription_id,
            metric=metric,
            entry_type="reserve",
            amount=amount,
            created_at=created,
            expires_at=None,
        ),
        LedgerEntrySnapshot(
            reservation_id=reservation_id,
            subscription_id=subscription_id,
            metric=metric,
            entry_type=cast("LedgerEntryType", entry_type),
            amount=amount,
            created_at=created,
            expires_at=None,
        ),
    ]


def balance(
    metric: UsageMetric,
    limit: int,
    entries: Iterable[LedgerEntrySnapshot],
) -> tuple[int, int, int]:
    result = compute_balance(metric, limit, entries, PERIOD_START, NOW)
    return result.used, result.reserved, result.remaining


def test_compute_balance_with_no_entries() -> None:
    # Given no ledger entries at all
    # When the balance is computed
    # Then the full limit is available
    assert balance("searches", 20, []) == (0, 0, 20)


def test_compute_balance_at_exact_limit() -> None:
    # Given confirmed usage equal to the limit
    # When the balance is computed
    # Then nothing remains
    assert balance("searches", 20, settled("confirm", 20)) == (20, 0, 0)


def test_compute_balance_over_limit_goes_negative() -> None:
    # Given confirmed usage beyond the limit (e.g. after a plan downgrade)
    # When the balance is computed
    # Then the remaining quota is negative
    assert balance("searches", 20, settled("confirm", 25)) == (25, 0, -5)


def test_compute_balance_nets_reserve_and_confirm() -> None:
    # Given one pending reservation and one confirmed reservation
    entries = pending(2) + settled("confirm", 1)

    # When the balance is computed
    # Then the confirm counts as used and the open reserve as reserved
    assert balance("searches", 20, entries) == (1, 2, 17)


def test_compute_balance_released_reservation_frees_quota() -> None:
    # Given a reservation that was released
    # When the balance is computed
    # Then the reservation no longer holds quota
    assert balance("searches", 20, settled("release", 3)) == (0, 0, 20)


def test_compute_balance_ignores_expired_reserves() -> None:
    # Given one expired reservation, one still-open, and one without expiry
    entries = (
        pending(4, expires_at=NOW - timedelta(seconds=1))
        + pending(3, expires_at=NOW + timedelta(seconds=1))
        + pending(2, expires_at=None)
    )

    # When the balance is computed
    # Then only unexpired reservations hold quota
    assert balance("searches", 20, entries) == (0, 5, 15)


def test_compute_balance_periodic_metric_ignores_entries_before_period_start() -> None:
    # Given confirmed usage and a reservation from a previous billing period
    before = PERIOD_START - timedelta(seconds=1)
    entries = settled("confirm", 10, created_at=before) + pending(5, created_at=before)
    entries += pending(6, created_at=PERIOD_START)

    # When the balance of a periodic metric is computed
    # Then only current-period entries count
    assert balance("searches", 20, entries) == (0, 6, 14)


def test_compute_balance_concurrent_metric_ignores_period_start() -> None:
    # Given a long-lived concurrent-metric confirm from before the period start
    entries = settled("confirm", 1, metric="owners", created_at=PERIOD_START - timedelta(days=30))

    # When the balance of a concurrent metric is computed
    # Then the entry still counts regardless of the billing period
    assert balance("owners", 1, entries) == (1, 0, 0)


def test_compute_balance_ignores_other_metrics() -> None:
    # Given entries for a different metric
    entries = settled("confirm", 5, metric="matches")

    # When the balance of searches is computed
    # Then the foreign metric does not count
    assert balance("searches", 20, entries) == (0, 0, 20)


def test_compute_balance_rejects_unknown_metric() -> None:
    # Given a metric outside the catalog
    # When the balance is computed
    # Then the metric is rejected before any accounting happens
    unknown = cast("UsageMetric", cast("object", "holograms"))
    with pytest.raises(UnknownMetricError):
        _ = compute_balance(unknown, 1, [], PERIOD_START, NOW)


def test_usage_metrics_catalog_order() -> None:
    # The canonical order drives summary rendering and must stay stable
    assert USAGE_METRICS == ("owners", "companies", "active_jobs", "searches", "matches", "reports")
