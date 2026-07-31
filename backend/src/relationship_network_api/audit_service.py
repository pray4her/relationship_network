import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.models import PlatformAuditEvent

AUDIT_RESULT_SUCCESS: Final = "success"
AUDIT_RESULT_FAILURE: Final = "failure"

AUDIT_LIST_LIMIT: Final = 200


@final
@dataclass(frozen=True)
class AuditEventView:
    """A recorded platform administration operation.

    actor_id is None when the acting user was deleted after the event.
    """

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    result: str
    detail: str
    created_at: datetime


def record_event(  # noqa: PLR0913
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    detail: str = "",
) -> None:
    """Append an audit event; the caller owns the surrounding transaction."""
    session.add(
        PlatformAuditEvent(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            detail=detail,
        )
    )


async def list_events(
    session: AsyncSession,
    *,
    limit: int = AUDIT_LIST_LIMIT,
) -> list[AuditEventView]:
    """Return the most recent audit events, newest first."""
    result = await session.execute(
        select(PlatformAuditEvent).order_by(PlatformAuditEvent.created_at.desc()).limit(limit)
    )
    return [
        AuditEventView(
            id=event.id,
            actor_id=event.actor_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            result=event.result,
            detail=event.detail,
            created_at=event.created_at,
        )
        for event in result.scalars()
    ]
