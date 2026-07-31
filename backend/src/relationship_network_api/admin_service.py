import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import audit_service, tenant_context
from relationship_network_api.models import (
    Tenant,
    TenantMembership,
    TenantStatus,
)

TENANT_NOT_FOUND_DETAIL: Final = "tenant_not_found"
TENANT_STATUS_UPDATE_ACTION: Final = "tenant.status_update"
_TARGET_TYPE_TENANT: Final = "tenant"

DEFAULT_SEARCH_LIMIT: Final = 50
MAX_SEARCH_LIMIT: Final = 100


@final
class TenantNotFoundError(Exception):
    """Raised when the requested tenant does not exist."""


@final
@dataclass(frozen=True)
class TenantSummaryView:
    """Tenant row in the platform administration tenant list."""

    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    member_count: int
    created_at: datetime


@final
@dataclass(frozen=True)
class TenantDetailView:
    """Full tenant overview for platform administrators."""

    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    mfa_required: bool
    member_count: int
    created_at: datetime


async def search_tenants(
    session: AsyncSession,
    *,
    query: str | None,
    status: TenantStatus | None,
    limit: int = DEFAULT_SEARCH_LIMIT,
    offset: int = 0,
) -> tuple[list[TenantSummaryView], int]:
    """Search tenants by name or slug, optionally filtered by lifecycle status."""
    # Membership rows are RLS-scoped; pin the platform admin read bypass first.
    await tenant_context.set_platform_admin_context(session)
    member_count = (
        select(func.count())
        .select_from(TenantMembership)
        .where(
            TenantMembership.tenant_id == Tenant.id,
            TenantMembership.is_active,
        )
        .correlate(Tenant)
        .scalar_subquery()
    )
    statement = select(Tenant, member_count.label("member_count"))
    count_statement = select(func.count()).select_from(Tenant)
    if query:
        pattern = f"%{query.strip()}%"
        condition = Tenant.name.ilike(pattern) | Tenant.slug.ilike(pattern)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    if status is not None:
        statement = statement.where(Tenant.status == status)
        count_statement = count_statement.where(Tenant.status == status)
    statement = statement.order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(statement)).all()
    total = (await session.execute(count_statement)).scalar_one()
    summaries = [
        TenantSummaryView(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            member_count=int(count),
            created_at=tenant.created_at,
        )
        for tenant, count in rows
    ]
    return summaries, int(total)


async def get_tenant_detail(session: AsyncSession, *, tenant_id: uuid.UUID) -> TenantDetailView:
    """Load a single tenant overview or refuse when it does not exist."""
    await tenant_context.set_platform_admin_context(session)
    tenant = await _load_tenant(session, tenant_id)
    return _detail_view(tenant, await _count_members(session, tenant.id))


async def update_tenant_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status: TenantStatus,
    actor_id: uuid.UUID,
) -> TenantDetailView:
    """Change a tenant's lifecycle status, auditing the outcome of the attempt."""
    await tenant_context.set_platform_admin_context(session)
    try:
        tenant = await _load_tenant(session, tenant_id)
    except TenantNotFoundError:
        audit_service.record_event(
            session,
            actor_id=actor_id,
            action=TENANT_STATUS_UPDATE_ACTION,
            target_type=_TARGET_TYPE_TENANT,
            target_id=str(tenant_id),
            result=audit_service.AUDIT_RESULT_FAILURE,
            detail=TENANT_NOT_FOUND_DETAIL,
        )
        await _commit(session)
        raise
    tenant.status = status
    audit_service.record_event(
        session,
        actor_id=actor_id,
        action=TENANT_STATUS_UPDATE_ACTION,
        target_type=_TARGET_TYPE_TENANT,
        target_id=str(tenant_id),
        result=audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"status={status}",
    )
    # Count before the commit: the platform admin GUC is transaction-local.
    view = _detail_view(tenant, await _count_members(session, tenant.id))
    await _commit(session)
    return view


def _detail_view(tenant: Tenant, member_count: int) -> TenantDetailView:
    return TenantDetailView(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        mfa_required=tenant.mfa_required,
        member_count=member_count,
        created_at=tenant.created_at,
    )


async def _load_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise TenantNotFoundError
    return tenant


async def _count_members(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    count = (
        await session.execute(
            select(func.count())
            .select_from(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )
    ).scalar_one()
    return int(count)


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
