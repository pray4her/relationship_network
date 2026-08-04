import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from relationship_network_api import audit_service, plan_service, tenant_context, usage_service
from relationship_network_api.models import OfflineOrder, Plan, PlanVersion, TenantSubscription
from relationship_network_api.plan_service import PlanNotFoundError

__all__ = [
    "BILLING_ORDER_CONFIRM_ACTION",
    "BILLING_ORDER_REJECT_ACTION",
    "OrderNotFoundError",
    "OrderStateError",
    "OrderStatus",
    "OrderView",
    "PlanNotFoundError",
    "confirm_order",
    "list_orders_admin",
    "list_tenant_orders",
    "reject_order",
    "submit_offline_order",
]

BILLING_ORDER_CONFIRM_ACTION: Final = "billing.order_confirm"
BILLING_ORDER_REJECT_ACTION: Final = "billing.order_reject"
_TARGET_TYPE_OFFLINE_ORDER: Final = "offline_order"

_CURRENT_SUBSCRIPTION_STATUSES: Final = ("trialing", "active")


_OrderRow = Row[tuple[OfflineOrder, PlanVersion, Plan]]


class OrderStatus(StrEnum):
    """Review states an offline order can be in."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@final
class OrderNotFoundError(Exception):
    """Raised when the requested offline order does not exist."""


@final
class OrderStateError(Exception):
    """Raised when an order review conflicts with its current state."""


@final
@dataclass(frozen=True)
class OrderView:
    """An offline order with the plan version it purchases."""

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


async def submit_offline_order(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    plan_code: str,
    amount_cents: int,
    payment_reference: str,
    payer_note: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> OrderView:
    """Submit an offline payment order for review, idempotently per idempotency key.

    The plan code resolves to its newest published version at submission time
    and the order pins that immutable version. Reusing an idempotency key with
    different order parameters raises IdempotencyKeyMismatchError.
    """
    resolved_now = now or datetime.now(UTC)
    version = await plan_service.get_latest_published_version(session, plan_code=plan_code)
    order = OfflineOrder(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_version_id=version.id,
        amount_cents=amount_cents,
        payment_reference=payment_reference,
        payer_note=payer_note,
        status="pending",
        idempotency_key=idempotency_key,
        submitted_by=user_id,
        created_at=resolved_now,
    )
    session.add(order)
    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        # A concurrent submission with the same idempotency key won the race;
        # return its order instead of double-billing. The commit/rollback ended
        # the transaction, so the tenant context must be set again before
        # reading through row level security.
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        winner = await _load_by_idempotency_key(
            session,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )
        if winner is None:
            raise
        _ensure_matching_request(
            winner,
            plan_version_id=version.id,
            amount_cents=amount_cents,
            payment_reference=payment_reference,
        )
        return _order_view(winner, version)
    except SQLAlchemyError:
        await session.rollback()
        raise
    return _order_view(order, version)


async def list_tenant_orders(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[OrderView]:
    """Return the tenant's offline orders, newest first."""
    result = await session.execute(
        _order_statement()
        .where(OfflineOrder.tenant_id == tenant_id)
        .order_by(OfflineOrder.created_at.desc())
    )
    return [_order_view_from_row(row) for row in result.all()]


async def list_orders_admin(
    session: AsyncSession,
    *,
    status: OrderStatus | None = None,
    tenant_id: uuid.UUID | None = None,
) -> list[OrderView]:
    """Return offline orders across tenants for platform administrators, newest first."""
    await tenant_context.set_platform_admin_context(session)
    statement = _order_statement().order_by(OfflineOrder.created_at.desc())
    if status is not None:
        statement = statement.where(OfflineOrder.status == status)
    if tenant_id is not None:
        statement = statement.where(OfflineOrder.tenant_id == tenant_id)
    result = await session.execute(statement)
    return [_order_view_from_row(row) for row in result.all()]


async def confirm_order(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    now: datetime | None = None,
) -> OrderView:
    """Confirm a pending order and activate its subscription; idempotent per order.

    The order review, the subscription activation, and the audit event commit
    in one transaction. Confirming an already confirmed order returns its
    current view without activating a second subscription; confirming a
    rejected order raises OrderStateError.
    """
    await tenant_context.set_platform_admin_context(session)
    resolved_now = now or datetime.now(UTC)
    order, version = await _load_order(session, order_id=order_id)
    if order.status == OrderStatus.CONFIRMED:
        return _order_view(order, version)
    if order.status == OrderStatus.REJECTED:
        raise OrderStateError
    order.status = "confirmed"
    order.reviewed_by = reviewer_id
    order.reviewed_at = resolved_now
    await _activate_subscription(
        session,
        tenant_id=order.tenant_id,
        plan_version_id=order.plan_version_id,
        order_id=order.id,
        now=resolved_now,
    )
    audit_service.record_event(
        session,
        actor_id=reviewer_id,
        action=BILLING_ORDER_CONFIRM_ACTION,
        target_type=_TARGET_TYPE_OFFLINE_ORDER,
        target_id=str(order.id),
        result=audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"tenant_id={order.tenant_id} plan={version.plan_code} v{version.version}",
    )
    await _commit(session)
    return _order_view(order, version)


async def reject_order(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    reason: str = "",
    now: datetime | None = None,
) -> OrderView:
    """Reject a pending order; idempotent per order.

    Rejecting an already rejected order returns its current view; rejecting a
    confirmed order raises OrderStateError because its subscription is live.
    """
    await tenant_context.set_platform_admin_context(session)
    resolved_now = now or datetime.now(UTC)
    order, version = await _load_order(session, order_id=order_id)
    if order.status == OrderStatus.REJECTED:
        return _order_view(order, version)
    if order.status == OrderStatus.CONFIRMED:
        raise OrderStateError
    order.status = "rejected"
    order.reviewed_by = reviewer_id
    order.reviewed_at = resolved_now
    order.review_note = reason
    audit_service.record_event(
        session,
        actor_id=reviewer_id,
        action=BILLING_ORDER_REJECT_ACTION,
        target_type=_TARGET_TYPE_OFFLINE_ORDER,
        target_id=str(order.id),
        result=audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"tenant_id={order.tenant_id} plan={version.plan_code} v{version.version}",
    )
    await _commit(session)
    return _order_view(order, version)


async def _activate_subscription(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan_version_id: uuid.UUID,
    order_id: uuid.UUID,
    now: datetime,
) -> None:
    """Replace the tenant's current subscription with one paid by the order.

    The caller owns the surrounding transaction; nothing commits here.

    Renewing while a paid subscription is still in period anchors the new
    period at the current period end, so prepaid time is never truncated.
    Trial conversion and resubscription after expiry start the paid period at
    confirmation time instead.
    """
    result = await session.execute(
        select(TenantSubscription).where(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status.in_(_CURRENT_SUBSCRIPTION_STATUSES),
        )
    )
    anchor = now
    for current in result.scalars():
        current.status = "cancelled"
        if current.trial_ends_at is None and current.current_period_end > now:
            anchor = current.current_period_end
    session.add(
        TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_version_id=plan_version_id,
            status="active",
            started_at=now,
            current_period_start=anchor,
            current_period_end=usage_service.add_one_month(anchor),
            trial_ends_at=None,
            offline_order_id=order_id,
        )
    )


async def _load_order(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
) -> tuple[OfflineOrder, plan_service.PlanVersionView]:
    result = await session.execute(_order_statement().where(OfflineOrder.id == order_id))
    row = result.first()
    if row is None:
        raise OrderNotFoundError
    return row[0], _version_view_from_row(row)


async def _load_by_idempotency_key(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    idempotency_key: str,
) -> OfflineOrder | None:
    result = await session.execute(
        select(OfflineOrder).where(
            OfflineOrder.tenant_id == tenant_id,
            OfflineOrder.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


def _ensure_matching_request(
    order: OfflineOrder,
    *,
    plan_version_id: uuid.UUID,
    amount_cents: int,
    payment_reference: str,
) -> None:
    """Reject an idempotency key reused with different order parameters."""
    if (
        order.plan_version_id != plan_version_id
        or order.amount_cents != amount_cents
        or order.payment_reference != payment_reference
    ):
        raise usage_service.IdempotencyKeyMismatchError


def _order_statement() -> Select[tuple[OfflineOrder, PlanVersion, Plan]]:
    return (
        select(OfflineOrder, PlanVersion, Plan)
        .join(PlanVersion, PlanVersion.id == OfflineOrder.plan_version_id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
    )


def _version_view_from_row(row: _OrderRow) -> plan_service.PlanVersionView:
    version = row[1]
    plan = row[2]
    return plan_service.PlanVersionView(
        id=version.id,
        plan_id=plan.id,
        plan_code=plan.code,
        plan_name=plan.name,
        version=version.version,
        status=version.status,
    )


def _order_view_from_row(row: _OrderRow) -> OrderView:
    order = row[0]
    return _order_view(order, _version_view_from_row(row))


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise


def _order_view(order: OfflineOrder, version: plan_service.PlanVersionView) -> OrderView:
    return OrderView(
        id=order.id,
        tenant_id=order.tenant_id,
        plan_code=version.plan_code,
        plan_version=version.version,
        amount_cents=order.amount_cents,
        payment_reference=order.payment_reference,
        payment_channel=order.payment_channel,
        payer_note=order.payer_note,
        status=OrderStatus(order.status),
        idempotency_key=order.idempotency_key,
        submitted_by=order.submitted_by,
        reviewed_by=order.reviewed_by,
        reviewed_at=order.reviewed_at,
        review_note=order.review_note,
        created_at=order.created_at,
    )
