import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, final

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.models import (
    USAGE_METRICS,
    Plan,
    PlanEntitlement,
    PlanVersion,
    PlanVersionStatus,
    UsageMetric,
)

TRIAL_PLAN_CODE: Final = "trial"
TRIAL_DURATION_DAYS: Final = 14

PLAN_NOT_FOUND_DETAIL: Final = "plan_not_found"
INCOMPLETE_ENTITLEMENTS_DETAIL: Final = "incomplete_entitlements"


@final
class PlanNotFoundError(Exception):
    """Raised when a plan or published plan version does not exist."""


@final
class IncompleteEntitlementsError(Exception):
    """Raised when an entitlement mapping does not cover exactly the usage metrics."""


@final
@dataclass(frozen=True)
class PlanVersionView:
    """A plan version with its owning plan."""

    id: uuid.UUID
    plan_id: uuid.UUID
    plan_code: str
    plan_name: str
    version: int
    status: PlanVersionStatus


def validate_entitlements(entitlements: Mapping[str, int]) -> dict[UsageMetric, int]:
    """Validate that the mapping covers exactly the six usage metrics."""
    unknown = set(entitlements) - set(USAGE_METRICS)
    missing = set(USAGE_METRICS) - set(entitlements)
    if unknown or missing:
        raise IncompleteEntitlementsError
    return {metric: entitlements[metric] for metric in USAGE_METRICS}


async def publish_plan_version(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    entitlements: Mapping[str, int],
) -> PlanVersionView:
    """Publish a new immutable plan version with a complete entitlement set.

    Concurrent publishers serialize on a transaction-scoped advisory lock so
    the computed max(version) + 1 cannot collide (the app role has no UPDATE
    privilege on plans, which rules out SELECT ... FOR UPDATE). Existing
    subscriptions stay pinned to their own version and are unaffected.
    """
    validated = validate_entitlements(entitlements)
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError
    _ = await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"plan_version_publish:{plan_id}"},
    )
    current_max = (
        await session.execute(
            select(func.max(PlanVersion.version)).where(PlanVersion.plan_id == plan_id)
        )
    ).scalar_one()
    version = PlanVersion(
        id=uuid.uuid4(),
        plan_id=plan.id,
        version=(current_max or 0) + 1,
        status="published",
    )
    session.add(version)
    try:
        # No ORM relationship links the tables, so flush the version row before
        # inserting its entitlements to satisfy the foreign key.
        await session.flush()
        session.add_all(
            PlanEntitlement(
                plan_version_id=version.id,
                metric=metric,
                limit_value=limit_value,
            )
            for metric, limit_value in validated.items()
        )
        await session.flush()
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    return _version_view(version, plan)


async def get_plan_entitlements(
    session: AsyncSession,
    *,
    plan_version_id: uuid.UUID,
) -> dict[UsageMetric, int]:
    """Return the entitlement limits pinned to a plan version."""
    result = await session.execute(
        select(PlanEntitlement.metric, PlanEntitlement.limit_value).where(
            PlanEntitlement.plan_version_id == plan_version_id
        )
    )
    return dict(result.tuples().all())


async def get_plan_version(
    session: AsyncSession,
    *,
    plan_version_id: uuid.UUID,
) -> PlanVersionView:
    """Return a plan version with its owning plan."""
    result = await session.execute(
        select(PlanVersion, Plan)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .where(PlanVersion.id == plan_version_id)
    )
    row = result.first()
    if row is None:
        raise PlanNotFoundError
    return _version_view(row[0], row[1])


async def get_latest_published_version(
    session: AsyncSession,
    *,
    plan_code: str,
) -> PlanVersionView:
    """Return the newest published version of a plan."""
    result = await session.execute(
        select(PlanVersion, Plan)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .where(Plan.code == plan_code, PlanVersion.status == "published")
        .order_by(PlanVersion.version.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise PlanNotFoundError
    return _version_view(row[0], row[1])


def _version_view(version: PlanVersion, plan: Plan) -> PlanVersionView:
    return PlanVersionView(
        id=version.id,
        plan_id=plan.id,
        plan_code=plan.code,
        plan_name=plan.name,
        version=version.version,
        status=version.status,
    )
