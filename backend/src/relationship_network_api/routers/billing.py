from datetime import datetime
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import usage_service
from relationship_network_api.deps import TenantContext, get_db_session, require_permission
from relationship_network_api.usage_service import (
    SUBSCRIPTION_NOT_FOUND_DETAIL,
    SubscriptionNotFoundError,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
BillingReadDep = Annotated[TenantContext, Depends(require_permission("billing:read"))]


@final
class PlanSummaryResponse(BaseModel):
    code: str
    name: str
    version: int


@final
class MetricBalanceResponse(BaseModel):
    metric: str
    limit: int
    used: int
    reserved: int
    remaining: int


@final
class BillingSummaryResponse(BaseModel):
    plan: PlanSummaryResponse
    status: str
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    metrics: list[MetricBalanceResponse]


@router.get("/billing/summary")
async def get_billing_summary(
    context: BillingReadDep,
    session: DbSession,
) -> BillingSummaryResponse:
    try:
        summary = await usage_service.get_usage_summary(session, tenant_id=context.tenant_id)
    except SubscriptionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SUBSCRIPTION_NOT_FOUND_DETAIL,
        ) from error
    subscription = summary.subscription
    return BillingSummaryResponse(
        plan=PlanSummaryResponse(
            code=subscription.plan_code,
            name=subscription.plan_name,
            version=subscription.plan_version,
        ),
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        metrics=[
            MetricBalanceResponse(
                metric=balance.metric,
                limit=balance.limit,
                used=balance.used,
                reserved=balance.reserved,
                remaining=balance.remaining,
            )
            for balance in summary.metrics
        ],
    )
