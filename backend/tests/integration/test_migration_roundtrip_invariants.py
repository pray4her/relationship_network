from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api.config import load_database_settings


@pytest.mark.anyio
@pytest.mark.integration
async def test_migrated_schema_restores_seed_rls_grants_indexes_and_legacy() -> None:
    engine = create_async_engine(str(load_database_settings().database_url))
    try:
        async with engine.connect() as connection:
            seed = (
                await connection.execute(
                    text(
                        """
                        SELECT versions.model, versions.prompt_version_id
                        FROM llm_configuration_current AS current
                        JOIN llm_configuration_versions AS versions
                          ON versions.id = current.version_id
                        WHERE current.singleton
                        """
                    )
                )
            ).one()
            job_columns = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = 'jobs'
                            """
                        )
                    )
                ).scalars()
            )
            trigger_exists = (
                await connection.execute(
                    text(
                        """
                        SELECT EXISTS (
                          SELECT 1 FROM pg_trigger
                          WHERE tgname = 'trg_jobs_reject_legacy_grant'
                        )
                        """
                    )
                )
            ).scalar_one()
            privileges = (
                await connection.execute(
                    text(
                        """
                        SELECT
                          has_table_privilege(
                            'relationship_app', 'platform_audit_events', 'SELECT'
                          ) AS app_audit_select,
                          has_table_privilege(
                            'relationship_app', 'platform_audit_events', 'INSERT'
                          ) AS app_audit_insert,
                          has_table_privilege(
                            'relationship_app', 'platform_audit_events', 'UPDATE'
                          ) AS app_audit_update,
                          has_table_privilege(
                            'relationship_app', 'platform_audit_events', 'DELETE'
                          ) AS app_audit_delete,
                          has_table_privilege(
                            'relationship_app', 'usage_ledger_entries', 'SELECT'
                          ) AS app_ledger_select,
                          has_table_privilege(
                            'relationship_app', 'usage_ledger_entries', 'INSERT'
                          ) AS app_ledger_insert,
                          has_table_privilege(
                            'relationship_app', 'usage_ledger_entries', 'UPDATE'
                          ) AS app_ledger_update,
                          has_table_privilege(
                            'relationship_app', 'job_requirement_versions', 'SELECT'
                          ) AS app_versions_select,
                          has_table_privilege(
                            'relationship_app', 'job_requirement_versions', 'INSERT'
                          ) AS app_versions_insert,
                          has_table_privilege(
                            'relationship_app', 'job_requirement_versions', 'UPDATE'
                          ) AS app_versions_update,
                          has_function_privilege(
                            'relationship_requirement_scheduler',
                            'schedule_due_requirement_tasks(integer)',
                            'EXECUTE'
                          ) AS scheduler_schedule,
                          has_function_privilege(
                            'relationship_requirement_scheduler',
                            'recover_expired_requirement_tasks(integer)',
                            'EXECUTE'
                          ) AS scheduler_recover,
                          has_function_privilege(
                            'relationship_outbox_dispatcher',
                            'claim_tenant_outbox_batch(uuid,integer,integer)',
                            'EXECUTE'
                          ) AS dispatcher_claim,
                          has_function_privilege(
                            'relationship_platform_worker',
                            'activate_llm_configuration_version(uuid,uuid)',
                            'EXECUTE'
                          ) AS worker_activate
                        """
                    )
                )
            ).one()
            rls_enabled = (
                await connection.execute(
                    text(
                        """
                        SELECT relrowsecurity
                        FROM pg_class
                        WHERE relname = 'job_requirement_versions'
                        """
                    )
                )
            ).scalar_one()
            indexes = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT indexname
                            FROM pg_indexes
                            WHERE schemaname = 'public'
                              AND indexname IN (
                                'uq_requirement_tasks_one_nonterminal',
                                'uq_requirement_drafts_one_editable',
                                'uq_llm_configuration_attempts_one_nonterminal'
                              )
                            """
                        )
                    )
                ).scalars()
            )

        assert seed.prompt_version_id in {
            "job-requirement-prompt-v1",
            "job-requirement-prompt-v2",
        }
        if seed.prompt_version_id == "job-requirement-prompt-v1":
            assert seed.model == "x-ai/grok-4.5"
        assert "legacy_requirement_exempt" in job_columns
        assert trigger_exists is True
        assert privileges.app_audit_select is True
        assert privileges.app_audit_insert is True
        assert privileges.app_audit_update is False
        assert privileges.app_audit_delete is False
        assert privileges.app_ledger_select is True
        assert privileges.app_ledger_insert is True
        assert privileges.app_ledger_update is False
        assert privileges.app_versions_select is True
        assert privileges.app_versions_insert is True
        assert privileges.app_versions_update is False
        assert privileges.scheduler_schedule is True
        assert privileges.scheduler_recover is True
        assert privileges.dispatcher_claim is True
        assert privileges.worker_activate is True
        assert rls_enabled is True
        assert {
            "uq_requirement_tasks_one_nonterminal",
            "uq_requirement_drafts_one_editable",
            "uq_llm_configuration_attempts_one_nonterminal",
        }.issubset(indexes)
    finally:
        await engine.dispose()
