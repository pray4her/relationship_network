import pytest

from relationship_network_api.models import USAGE_METRICS
from relationship_network_api.plan_service import (
    TRIAL_DURATION_DAYS,
    TRIAL_PLAN_CODE,
    IncompleteEntitlementsError,
    validate_entitlements,
)

FULL_ENTITLEMENTS = {
    "owners": 1,
    "companies": 1,
    "active_jobs": 2,
    "searches": 20,
    "matches": 3,
    "reports": 1,
}


def test_validate_entitlements_accepts_the_exact_metric_set() -> None:
    # Given a mapping covering exactly the six usage metrics
    # When the entitlements are validated
    validated = validate_entitlements(FULL_ENTITLEMENTS)

    # Then every metric keeps its limit
    assert validated == FULL_ENTITLEMENTS


def test_validate_entitlements_rejects_a_missing_metric() -> None:
    # Given a mapping missing one usage metric
    incomplete = {metric: 1 for metric in USAGE_METRICS if metric != "reports"}

    # When the entitlements are validated
    # Then the gap is rejected
    with pytest.raises(IncompleteEntitlementsError):
        _ = validate_entitlements(incomplete)


def test_validate_entitlements_rejects_an_unknown_metric() -> None:
    # Given a mapping with an extra unknown metric
    unknown = {**FULL_ENTITLEMENTS, "holograms": 9}

    # When the entitlements are validated
    # Then the unknown metric is rejected
    with pytest.raises(IncompleteEntitlementsError):
        _ = validate_entitlements(unknown)


def test_trial_plan_constants() -> None:
    # The trial plan code and duration anchor registration and the seed migration
    assert TRIAL_PLAN_CODE == "trial"
    assert TRIAL_DURATION_DAYS == 14
