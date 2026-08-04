"""Append-only tenant business audit events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.models import TenantAuditEvent

AUDIT_RESULT_SUCCESS: Final = "success"
AUDIT_RESULT_FAILURE: Final = "failure"
AUDIT_LIST_LIMIT: Final = 200
TARGET_TYPE_COMPANY: Final = "company"


@final
@dataclass(frozen=True)
class TenantAuditEventView:
    """A recorded tenant business operation."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    result: str
    detail: str
    created_at: datetime


def record_event(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    detail: str = "",
) -> None:
    """Append a tenant audit event; the caller owns the surrounding transaction."""
    session.add(
        TenantAuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            detail=detail,
        )
    )


async def list_events_for_target(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    target_type: str,
    target_id: str,
    limit: int = AUDIT_LIST_LIMIT,
) -> list[TenantAuditEventView]:
    """Return recent audit events for one target within the tenant, newest first."""
    result = await session.execute(
        select(TenantAuditEvent)
        .where(
            TenantAuditEvent.tenant_id == tenant_id,
            TenantAuditEvent.target_type == target_type,
            TenantAuditEvent.target_id == target_id,
        )
        .order_by(TenantAuditEvent.created_at.desc())
        .limit(limit)
    )
    return [_view(event) for event in result.scalars()]


def _view(event: TenantAuditEvent) -> TenantAuditEventView:
    return TenantAuditEventView(
        id=event.id,
        tenant_id=event.tenant_id,
        actor_user_id=event.actor_user_id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        result=event.result,
        detail=event.detail,
        created_at=event.created_at,
    )
