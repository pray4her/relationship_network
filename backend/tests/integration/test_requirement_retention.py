# pyright: reportImplicitStringConcatenation=false

"""Integration coverage for the 90-day requirement input body retention path."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api.config import load_database_settings

_SNAPSHOT_SQL = """
INSERT INTO job_requirement_input_snapshots
    (id, tenant_id, job_id, configuration_version_id, total_characters, content_sha256, created_at)
VALUES
    (:id, :tenant_id, :job_id, :configuration_id, 4, repeat('c', 64), :created_at)
"""

_SOURCE_SQL = """
INSERT INTO job_requirement_input_sources
    (id, tenant_id, job_id, snapshot_id, source_id, source_kind, position,
     original_text, corrected_text, sent_text, original_sha256, sent_sha256, unicode_characters)
VALUES
    (:id, :tenant_id, :job_id, :snapshot_id, 'job-description', 'job-description', 0,
     '原始正文', '修正正文', '发送正文', repeat('a', 64), repeat('b', 64), 4)
"""


@pytest.mark.anyio
@pytest.mark.integration
async def test_requirement_input_body_retention_permissions_and_scope() -> None:  # noqa: PLR0915
    engine = create_async_engine(str(load_database_settings().database_url))
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    job_keep_id = uuid.uuid4()
    job_purge_id = uuid.uuid4()
    job_fresh_id = uuid.uuid4()
    snapshot_keep_id = uuid.uuid4()
    snapshot_purge_id = uuid.uuid4()
    snapshot_fresh_id = uuid.uuid4()
    source_keep_id = uuid.uuid4()
    source_purge_id = uuid.uuid4()
    source_fresh_id = uuid.uuid4()
    draft_keep_id = uuid.uuid4()
    version_keep_id = uuid.uuid4()
    task_purge_id = uuid.uuid4()
    upgrade_id = uuid.uuid4()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                current_version_id = (
                    await connection.execute(
                        text("SELECT version_id FROM llm_configuration_current WHERE singleton")
                    )
                ).scalar_one()
                _ = await connection.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug) VALUES "
                        "(:tenant_id, 'Retention tenant', :slug)"
                    ),
                    {"slug": f"retention-{tenant_id.hex}", "tenant_id": tenant_id},
                )
                _ = await connection.execute(
                    text(
                        "INSERT INTO companies (id, tenant_id, name) VALUES "
                        "(:company_id, :tenant_id, 'Retention company')"
                    ),
                    {"company_id": company_id, "tenant_id": tenant_id},
                )
                for job_id in (job_keep_id, job_purge_id, job_fresh_id):
                    _ = await connection.execute(
                        text(
                            "INSERT INTO jobs (id, tenant_id, company_id, title, description) "
                            "VALUES (:job_id, :tenant_id, :company_id, 'Retention job', '正文')"
                        ),
                        {
                            "company_id": company_id,
                            "job_id": job_id,
                            "tenant_id": tenant_id,
                        },
                    )
                aged = "now() - interval '91 days'"
                for snapshot_id, job_id, created_at in (
                    (snapshot_keep_id, job_keep_id, aged),
                    (snapshot_purge_id, job_purge_id, aged),
                    (snapshot_fresh_id, job_fresh_id, "now()"),
                ):
                    _ = await connection.execute(
                        text(_SNAPSHOT_SQL.replace(":created_at", created_at)),
                        {
                            "configuration_id": current_version_id,
                            "id": snapshot_id,
                            "job_id": job_id,
                            "tenant_id": tenant_id,
                        },
                    )
                for source_id, snapshot_id, job_id in (
                    (source_keep_id, snapshot_keep_id, job_keep_id),
                    (source_purge_id, snapshot_purge_id, job_purge_id),
                    (source_fresh_id, snapshot_fresh_id, job_fresh_id),
                ):
                    _ = await connection.execute(
                        text(_SOURCE_SQL),
                        {
                            "id": source_id,
                            "job_id": job_id,
                            "snapshot_id": snapshot_id,
                            "tenant_id": tenant_id,
                        },
                    )
                _ = await connection.execute(
                    text(
                        "INSERT INTO job_requirement_drafts "
                        "(id, tenant_id, job_id, requirement_schema_version_id, result_json, "
                        "status, revision) VALUES "
                        "(:id, :tenant_id, :job_id, 'job-requirement-schema-v1', "
                        "jsonb_build_object(), 'confirmed', 2)"
                    ),
                    {"id": draft_keep_id, "job_id": job_keep_id, "tenant_id": tenant_id},
                )
                _ = await connection.execute(
                    text(
                        "INSERT INTO job_requirement_versions "
                        "(id, tenant_id, job_id, version_number, requirement_schema_version_id, "
                        "result_json, draft_id, input_snapshot_id) VALUES "
                        "(:id, :tenant_id, :job_id, 1, 'job-requirement-schema-v1', "
                        "jsonb_build_object(), :draft_id, :snapshot_id)"
                    ),
                    {
                        "draft_id": draft_keep_id,
                        "id": version_keep_id,
                        "job_id": job_keep_id,
                        "snapshot_id": snapshot_keep_id,
                        "tenant_id": tenant_id,
                    },
                )
                _ = await connection.execute(
                    text(
                        "INSERT INTO job_requirement_parsing_tasks "
                        "(id, tenant_id, job_id, input_snapshot_id, configuration_version_id, "
                        "idempotency_key, effective_request_sha256, status, error_code, "
                        "completed_at) VALUES "
                        "(:id, :tenant_id, :job_id, :snapshot_id, :configuration_id, "
                        ":idempotency_key, repeat('d', 64), 'failed', "
                        "'requirement_temporary_failure', now())"
                    ),
                    {
                        "configuration_id": current_version_id,
                        "id": task_purge_id,
                        "idempotency_key": str(task_purge_id),
                        "job_id": job_purge_id,
                        "snapshot_id": snapshot_purge_id,
                        "tenant_id": tenant_id,
                    },
                )

                _ = await connection.execute(
                    text("SET LOCAL ROLE relationship_requirement_maintenance")
                )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text("SELECT * FROM job_requirement_input_sources")
                        )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(text("SELECT * FROM job_requirement_drafts"))
                purged = (
                    await connection.execute(
                        text("SELECT cleanup_expired_requirement_input_bodies(100)")
                    )
                ).scalar_one()
                assert purged == 1
                second_run = (
                    await connection.execute(
                        text("SELECT cleanup_expired_requirement_input_bodies(100)")
                    )
                ).scalar_one()
                assert second_run == 0

                _ = await connection.execute(text("RESET ROLE"))
                kept = (
                    await connection.execute(
                        text(
                            "SELECT original_text, corrected_text, sent_text, body_purged_at "
                            "FROM job_requirement_input_sources WHERE id = :id"
                        ),
                        {"id": source_keep_id},
                    )
                ).one()
                assert kept.original_text == "原始正文"
                assert kept.corrected_text == "修正正文"
                assert kept.sent_text == "发送正文"
                assert kept.body_purged_at is None
                fresh = (
                    await connection.execute(
                        text(
                            "SELECT original_text, body_purged_at "
                            "FROM job_requirement_input_sources WHERE id = :id"
                        ),
                        {"id": source_fresh_id},
                    )
                ).one()
                assert fresh.original_text == "原始正文"
                assert fresh.body_purged_at is None
                purged_row = (
                    await connection.execute(
                        text(
                            "SELECT original_text, corrected_text, sent_text, body_purged_at, "
                            "original_sha256, sent_sha256, unicode_characters, snapshot_id "
                            "FROM job_requirement_input_sources WHERE id = :id"
                        ),
                        {"id": source_purge_id},
                    )
                ).one()
                assert purged_row.original_text is None
                assert purged_row.corrected_text is None
                assert purged_row.sent_text is None
                assert purged_row.body_purged_at is not None
                assert len(purged_row.original_sha256) == 64
                assert len(purged_row.sent_sha256) == 64
                assert purged_row.unicode_characters == 4
                assert purged_row.snapshot_id == snapshot_purge_id
                task_linkage = (
                    await connection.execute(
                        text(
                            "SELECT count(*) FROM job_requirement_parsing_tasks "
                            "WHERE id = :task_id AND input_snapshot_id = :snapshot_id"
                        ),
                        {"snapshot_id": snapshot_purge_id, "task_id": task_purge_id},
                    )
                ).scalar_one()
                assert task_linkage == 1

                _ = await connection.execute(text("SET LOCAL ROLE relationship_app"))
                _ = await connection.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                _ = await connection.execute(
                    text(
                        "INSERT INTO job_requirement_draft_schema_upgrades "
                        "(id, tenant_id, job_id, draft_id, from_schema_version_id, "
                        "to_schema_version_id, converter_version, pre_upgrade_json, "
                        "item_mappings) VALUES "
                        "(:id, :tenant_id, :job_id, :draft_id, 'job-requirement-schema-v1', "
                        "'job-requirement-schema-v2', 'v1-to-v2@1', jsonb_build_object(), "
                        "'[]'::jsonb)"
                    ),
                    {
                        "draft_id": draft_keep_id,
                        "id": upgrade_id,
                        "job_id": job_keep_id,
                        "tenant_id": tenant_id,
                    },
                )
                column_update = await connection.execute(
                    text(
                        "UPDATE job_requirement_draft_schema_upgrades "
                        "SET lossy_resolutions = CAST(:resolutions AS jsonb) WHERE id = :id"
                    ),
                    {
                        "id": upgrade_id,
                        "resolutions": '[{"item_id": "hard-1", "resolution": null}]',
                    },
                )
                assert column_update.rowcount == 1
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "UPDATE job_requirement_draft_schema_upgrades "
                                "SET converter_version = 'changed' WHERE id = :id"
                            ),
                            {"id": upgrade_id},
                        )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "DELETE FROM job_requirement_draft_schema_upgrades WHERE id = :id"
                            ),
                            {"id": upgrade_id},
                        )
                for statement in (
                    "UPDATE tenant_audit_events SET detail = 'changed' WHERE id = :id",
                    "DELETE FROM tenant_audit_events WHERE id = :id",
                    "UPDATE platform_audit_events SET detail = 'changed' WHERE id = :id",
                    "DELETE FROM platform_audit_events WHERE id = :id",
                ):
                    with pytest.raises(DBAPIError):
                        async with connection.begin_nested():
                            _ = await connection.execute(
                                text(statement),
                                {"id": uuid.uuid4()},
                            )

                _ = await connection.execute(text("SELECT set_config('app.tenant_id', '', true)"))
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM job_requirement_input_sources")
                    )
                ).scalar_one() == 0
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM job_requirement_draft_schema_upgrades")
                    )
                ).scalar_one() == 0
                _ = await connection.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(other_tenant_id)},
                )
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM job_requirement_input_sources")
                    )
                ).scalar_one() == 0
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
