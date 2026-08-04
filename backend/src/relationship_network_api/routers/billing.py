import uuid
from datetime import datetime
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import order_service, plan_service, usage_service
from relationship_network_api.deps import TenantContext, get_db_session, require_permission
from relationship_network_api.order_service import OrderStatus
from relationship_network_api.usage_service import (
    IDEMPOTENCY_KEY_MISMATCH_DETAIL,
    SUBSCRIPTION_NOT_FOUND_DETAIL,
    IdempotencyKeyMismatchError,
    SubscriptionNotFoundError,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
BillingReadDep = Annotated[TenantContext, Depends(require_permission("billing:read"))]
BillingManageDep = Annotated[TenantContext, Depends(require_permission("billing:manage"))]


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


@final
class OrderCreateRequest(BaseModel):
    plan_code: str = Field(min_length=1)
    amount_cents: int = Field(ge=0)
    payment_reference: str = Field(min_length=1, max_length=200)
    payer_note: str = Field(default="", max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


@final
class OrderResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_code: str
    plan_version: int
    amount_cents: int
    payment_reference: str
    payment_channel: str
    payer_note: str
    status: OrderStatus
    idempotency_key: str
    submitted_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str
    created_at: datetime


@final
class OrderListResponse(BaseModel):
    orders: list[OrderResponse]


@final
class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_code: str
    plan_name: str
    plan_version: int
    status: str
    started_at: datetime
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    cancel_requested_at: datetime | None
    offline_order_id: uuid.UUID | None


def order_response(view: order_service.OrderView) -> OrderResponse:
    """Serialize an order view into its API response shape."""
    return OrderResponse(
        id=view.id,
        tenant_id=view.tenant_id,
        plan_code=view.plan_code,
        plan_version=view.plan_version,
        amount_cents=view.amount_cents,
        payment_reference=view.payment_reference,
        payment_channel=view.payment_channel,
        payer_note=view.payer_note,
        status=view.status,
        idempotency_key=view.idempotency_key,
        submitted_by=view.submitted_by,
        reviewed_by=view.reviewed_by,
        reviewed_at=view.reviewed_at,
        review_note=view.review_note,
        created_at=view.created_at,
    )


def _subscription_response(view: usage_service.SubscriptionView) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=view.id,
        tenant_id=view.tenant_id,
        plan_code=view.plan_code,
        plan_name=view.plan_name,
        plan_version=view.plan_version,
        status=view.status,
        started_at=view.started_at,
        trial_ends_at=view.trial_ends_at,
        current_period_start=view.current_period_start,
        current_period_end=view.current_period_end,
        cancel_requested_at=view.cancel_requested_at,
        offline_order_id=view.offline_order_id,
    )


@router.post("/billing/orders", status_code=status.HTTP_201_CREATED)
async def submit_offline_order(
    payload: OrderCreateRequest,
    context: BillingManageDep,
    session: DbSession,
) -> OrderResponse:
    try:
        view = await order_service.submit_offline_order(
            session,
            tenant_id=context.tenant_id,
            user_id=context.authentication.user.id,
            plan_code=payload.plan_code,
            amount_cents=payload.amount_cents,
            payment_reference=payload.payment_reference,
            payer_note=payload.payer_note,
            idempotency_key=payload.idempotency_key,
        )
    except plan_service.PlanNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=plan_service.PLAN_NOT_FOUND_DETAIL,
        ) from error
    except IdempotencyKeyMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=IDEMPOTENCY_KEY_MISMATCH_DETAIL,
        ) from error
    return order_response(view)


@router.get("/billing/orders")
async def list_tenant_orders(
    context: BillingReadDep,
    session: DbSession,
) -> OrderListResponse:
    orders = await order_service.list_tenant_orders(session, tenant_id=context.tenant_id)
    return OrderListResponse(orders=[order_response(view) for view in orders])


@router.post("/billing/subscription/cancel")
async def cancel_subscription(
    context: BillingManageDep,
    session: DbSession,
) -> SubscriptionResponse:
    try:
        view = await usage_service.cancel_subscription(session, tenant_id=context.tenant_id)
    except SubscriptionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SUBSCRIPTION_NOT_FOUND_DETAIL,
        ) from error
    return _subscription_response(view)
