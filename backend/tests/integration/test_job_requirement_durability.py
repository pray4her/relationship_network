"""Database privilege boundaries for tenant requirement task durability."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api.config import load_database_settings


@pytest.mark.anyio
@pytest.mark.integration
async def test_requirement_scheduler_and_dispatcher_have_only_fixed_function_access() -> None:
    engine = create_async_engine(str(load_database_settings().database_url))
    try:
        async with engine.connect() as connection:
            privileges = (
                await connection.execute(
                    text(
                        """
                        SELECT
                          has_function_privilege(
                            'relationship_requirement_scheduler',
                            'schedule_due_requirement_tasks(integer)',
                            'EXECUTE'
                          ) AS scheduler_can_schedule,
                          has_function_privilege(
                            'relationship_requirement_scheduler',
                            'recover_expired_requirement_tasks(integer)',
                            'EXECUTE'
                          ) AS scheduler_can_recover,
                          has_table_privilege(
                            'relationship_requirement_scheduler',
                            'job_requirement_parsing_tasks',
                            'SELECT'
                          ) AS scheduler_can_select_tasks,
                          has_function_privilege(
                            'relationship_outbox_dispatcher',
                            'claim_tenant_outbox_batch(uuid,integer,integer)',
                            'EXECUTE'
                          ) AS dispatcher_can_claim,
                          has_function_privilege(
                            'relationship_outbox_dispatcher',
                            'enqueue_delayed_requirement_task(uuid,uuid,integer)',
                            'EXECUTE'
                          ) AS dispatcher_can_enqueue,
                          has_table_privilege(
                            'relationship_outbox_dispatcher',
                            'job_requirement_parsing_tasks',
                            'SELECT'
                          ) AS dispatcher_can_select_tasks,
                          has_function_privilege(
                            'relationship_app',
                            'enqueue_delayed_requirement_task(uuid,uuid,integer)',
                            'EXECUTE'
                          ) AS app_can_enqueue
                        """
                    )
                )
            ).one()

        assert privileges.scheduler_can_schedule is True
        assert privileges.scheduler_can_recover is True
        assert privileges.scheduler_can_select_tasks is False
        assert privileges.dispatcher_can_claim is True
        assert privileges.dispatcher_can_enqueue is False
        assert privileges.dispatcher_can_select_tasks is False
        assert privileges.app_can_enqueue is True
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_requirement_task_schema_has_idempotency_and_lease_invariants() -> None:
    engine = create_async_engine(str(load_database_settings().database_url))
    try:
        async with engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'job_requirement_parsing_tasks'
                            """
                        )
                    )
                ).scalars()
            )
            constraints = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT conname
                            FROM pg_constraint
                            WHERE conrelid = 'job_requirement_parsing_tasks'::regclass
                            """
                        )
                    )
                ).scalars()
            )

        assert {
            "idempotency_key",
            "effective_request_sha256",
            "structured_invalid_count",
            "lease_token",
            "lease_expires_at",
            "last_heartbeat_at",
            "next_attempt_at",
            "updated_at",
        }.issubset(columns)
        assert {
            "uq_requirement_tasks_tenant_idempotency",
            "ck_requirement_tasks_call_budget",
            "ck_requirement_tasks_structured_invalid_budget",
        }.issubset(constraints)
    finally:
        await engine.dispose()
