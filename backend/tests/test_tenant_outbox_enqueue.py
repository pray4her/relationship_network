"""Tenant Outbox writers must not rely on RETURNING (app role has INSERT only)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Insert

from relationship_network_api.job_requirement_service import enqueue_tenant_outbox

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.executed: list[object] = []

    def add(self, entity: object) -> None:
        self.added.append(entity)

    async def execute(self, statement: object) -> None:
        self.executed.append(statement)


@pytest.mark.anyio
async def test_enqueue_tenant_outbox_uses_inline_insert_without_returning() -> None:
    session = _RecordingSession()
    tenant_id = uuid.uuid4()
    task_id = uuid.uuid4()

    await enqueue_tenant_outbox(
        cast("AsyncSession", cast("object", session)),
        tenant_id=tenant_id,
        task_id=task_id,
        topic="job_requirement_parsing.process",
        aggregate_id=task_id,
    )

    assert session.added == []
    assert len(session.executed) == 1
    statement = session.executed[0]
    assert isinstance(statement, Insert)
    compiled = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False})
    )
    assert "RETURNING" not in compiled.upper()
