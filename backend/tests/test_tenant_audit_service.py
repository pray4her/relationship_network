"""Unit tests for tenant business audit recording and listing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_audit_service
from relationship_network_api.models import TenantAuditEvent
from relationship_network_api.tenant_audit_service import (
    AUDIT_RESULT_SUCCESS,
    TARGET_TYPE_COMPANY,
    TenantAuditEventView,
)


pytestmark = pytest.mark.anyio


class SpySession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self._rows: list[TenantAuditEvent] = []

    def add(self, item: object) -> None:
        self.added.append(item)
        if isinstance(item, TenantAuditEvent):
            self._rows.append(item)

    async def execute(self, _statement: object) -> Any:
        ordered = sorted(
            self._rows,
            key=lambda row: row.created_at or datetime.now(UTC),
            reverse=True,
        )
        return SimpleNamespace(scalars=lambda: ordered)


async def test_record_and_list_company_events() -> None:
    session = SpySession()
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    company_id = uuid.uuid4()

    tenant_audit_service.record_event(
        cast("AsyncSession", session),
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="company.create",
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
        result=AUDIT_RESULT_SUCCESS,
        detail="Acme",
    )
    assert len(session.added) == 1
    event = cast("TenantAuditEvent", session.added[0])
    event.created_at = datetime.now(UTC)

    events = await tenant_audit_service.list_events_for_target(
        cast("AsyncSession", session),
        tenant_id=tenant_id,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
    )
    assert len(events) == 1
    assert isinstance(events[0], TenantAuditEventView)
    assert events[0].action == "company.create"
    assert events[0].detail == "Acme"
