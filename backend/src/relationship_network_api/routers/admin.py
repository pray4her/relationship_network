import uuid
from datetime import datetime
from typing import Annotated, Final, final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import admin_service, audit_service, order_service
from relationship_network_api.auth_service import Authentication
from relationship_network_api.deps import (
    get_db_session,
    require_platform_admin,
)
from relationship_network_api.models import TenantStatus
from relationship_network_api.order_service import OrderStatus
from relationship_network_api.routers.billing import (
    OrderListResponse,
    OrderResponse,
    order_response,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
PlatformAdminDep = Annotated[Authentication, Depends(require_platform_admin)]

_QUERY_MAX_LENGTH: Final = 100
ORDER_NOT_FOUND_DETAIL: Final = "order_not_found"
ORDER_ALREADY_REJECTED_DETAIL: Final = "order_already_rejected"
ORDER_ALREADY_CONFIRMED_DETAIL: Final = "order_already_confirmed"


@final
class TenantSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    member_count: int
    created_at: datetime


@final
class TenantListResponse(BaseModel):
    tenants: list[TenantSummaryResponse]
    total: int


@final
class TenantDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    mfa_required: bool
    member_count: int
    created_at: datetime


@final
class UpdateTenantStatusRequest(BaseModel):
    status: TenantStatus


@final
class AuditEventResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    result: str
    detail: str
    created_at: datetime


@final
class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]


def _summary_response(view: admin_service.TenantSummaryView) -> TenantSummaryResponse:
    return TenantSummaryResponse(
        id=view.id,
        name=view.name,
        slug=view.slug,
        status=view.status,
        member_count=view.member_count,
        created_at=view.created_at,
    )


def _detail_response(view: admin_service.TenantDetailView) -> TenantDetailResponse:
    return TenantDetailResponse(
        id=view.id,
        name=view.name,
        slug=view.slug,
        status=view.status,
        mfa_required=view.mfa_required,
        member_count=view.member_count,
        created_at=view.created_at,
    )


@router.get("/admin/tenants")
async def search_tenants(
    _admin: PlatformAdminDep,
    session: DbSession,
    query: Annotated[str | None, Query(max_length=_QUERY_MAX_LENGTH)] = None,
    tenant_status: Annotated[TenantStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=admin_service.MAX_SEARCH_LIMIT)] = (
        admin_service.DEFAULT_SEARCH_LIMIT
    ),
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TenantListResponse:
    tenants, total = await admin_service.search_tenants(
        session,
        query=query,
        status=tenant_status,
        limit=limit,
        offset=offset,
    )
    return TenantListResponse(
        tenants=[_summary_response(view) for view in tenants],
        total=total,
    )


@router.get("/admin/tenants/{tenant_id}")
async def read_tenant(
    tenant_id: uuid.UUID,
    _admin: PlatformAdminDep,
    session: DbSession,
) -> TenantDetailResponse:
    try:
        view = await admin_service.get_tenant_detail(session, tenant_id=tenant_id)
    except admin_service.TenantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=admin_service.TENANT_NOT_FOUND_DETAIL,
        ) from error
    return _detail_response(view)


@router.post("/admin/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: uuid.UUID,
    payload: UpdateTenantStatusRequest,
    admin: PlatformAdminDep,
    session: DbSession,
) -> TenantDetailResponse:
    try:
        view = await admin_service.update_tenant_status(
            session,
            tenant_id=tenant_id,
            status=payload.status,
            actor_id=admin.user.id,
        )
    except admin_service.TenantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=admin_service.TENANT_NOT_FOUND_DETAIL,
        ) from error
    return _detail_response(view)


@router.get("/admin/audit-events")
async def list_audit_events(
    _admin: PlatformAdminDep,
    session: DbSession,
) -> AuditEventListResponse:
    events = await audit_service.list_events(session)
    return AuditEventListResponse(
        events=[
            AuditEventResponse(
                id=event.id,
                actor_id=event.actor_id,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                result=event.result,
                detail=event.detail,
                created_at=event.created_at,
            )
            for event in events
        ]
    )


@final
class RejectOrderRequest(BaseModel):
    reason: str = ""


@router.get("/admin/orders")
async def list_orders(
    _admin: PlatformAdminDep,
    session: DbSession,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    tenant_id: uuid.UUID | None = None,
) -> OrderListResponse:
    orders = await order_service.list_orders_admin(
        session,
        status=order_status,
        tenant_id=tenant_id,
    )
    return OrderListResponse(orders=[order_response(view) for view in orders])


@router.post("/admin/orders/{order_id}/confirm")
async def confirm_order(
    order_id: uuid.UUID,
    admin: PlatformAdminDep,
    session: DbSession,
) -> OrderResponse:
    try:
        view = await order_service.confirm_order(
            session,
            order_id=order_id,
            reviewer_id=admin.user.id,
        )
    except order_service.OrderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ORDER_NOT_FOUND_DETAIL,
        ) from error
    except order_service.OrderStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ORDER_ALREADY_REJECTED_DETAIL,
        ) from error
    return order_response(view)


@router.post("/admin/orders/{order_id}/reject")
async def reject_order(
    order_id: uuid.UUID,
    payload: RejectOrderRequest,
    admin: PlatformAdminDep,
    session: DbSession,
) -> OrderResponse:
    try:
        view = await order_service.reject_order(
            session,
            order_id=order_id,
            reviewer_id=admin.user.id,
            reason=payload.reason,
        )
    except order_service.OrderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ORDER_NOT_FOUND_DETAIL,
        ) from error
    except order_service.OrderStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ORDER_ALREADY_CONFIRMED_DETAIL,
        ) from error
    return order_response(view)
