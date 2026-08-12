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
            "replaces_draft_id",
            "replaces_draft_revision",
        }.issubset(columns)
        assert {
            "uq_requirement_tasks_tenant_idempotency",
            "ck_requirement_tasks_call_budget",
            "ck_requirement_tasks_structured_invalid_budget",
            "ck_requirement_tasks_replaced_draft",
            "fk_requirement_tasks_replaced_draft_tenant_job",
        }.issubset(constraints)
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_requirement_draft_schema_has_editing_and_single_editable_invariants() -> None:
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
                              AND table_name = 'job_requirement_drafts'
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
                            WHERE conrelid = 'job_requirement_drafts'::regclass
                            """
                        )
                    )
                ).scalars()
            )
            indexes = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT indexname
                            FROM pg_indexes
                            WHERE schemaname = 'public'
                              AND tablename = 'job_requirement_drafts'
                            """
                        )
                    )
                ).scalars()
            )
            schema_constraints = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT conname
                            FROM pg_constraint
                            WHERE conrelid = 'job_requirement_schema_versions'::regclass
                            """
                        )
                    )
                ).scalars()
            )

        assert {"updated_by", "status_changed_at"}.issubset(columns)
        assert "uq_requirement_drafts_id_tenant_job" in constraints
        assert "uq_requirement_drafts_one_editable" in indexes
        assert "ck_requirement_schema_versions_editor_asset" in schema_constraints
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.integration
async def test_requirement_versions_are_immutable_and_gated() -> None:
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
                              AND table_name = 'job_requirement_versions'
                            """
                        )
                    )
                ).scalars()
            )
            job_columns = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'jobs'
                            """
                        )
                    )
                ).scalars()
            )
            privileges = (
                await connection.execute(
                    text(
                        """
                        SELECT
                          has_table_privilege(
                            'relationship_app',
                            'job_requirement_versions',
                            'SELECT'
                          ) AS can_select,
                          has_table_privilege(
                            'relationship_app',
                            'job_requirement_versions',
                            'INSERT'
                          ) AS can_insert,
                          has_table_privilege(
                            'relationship_app',
                            'job_requirement_versions',
                            'UPDATE'
                          ) AS can_update,
                          has_table_privilege(
                            'relationship_app',
                            'job_requirement_versions',
                            'DELETE'
                          ) AS can_delete
                        """
                    )
                )
            ).one()
            constraints = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT conname
                            FROM pg_constraint
                            WHERE conrelid = 'jobs'::regclass
                               OR conrelid = 'job_requirement_versions'::regclass
                            """
                        )
                    )
                ).scalars()
            )

        assert {
            "version_number",
            "result_json",
            "draft_id",
            "source_version_id",
            "confirmed_by",
            "confirmed_at",
        }.issubset(columns)
        assert {"current_requirement_version_id", "legacy_requirement_exempt"}.issubset(job_columns)
        assert privileges.can_select is True
        assert privileges.can_insert is True
        assert privileges.can_update is False
        assert privileges.can_delete is False
        assert "ck_jobs_active_requires_requirement_version" in constraints
        assert "uq_requirement_versions_tenant_job_number" in constraints
        assert "fk_jobs_current_requirement_version" in constraints
    finally:
        await engine.dispose()
