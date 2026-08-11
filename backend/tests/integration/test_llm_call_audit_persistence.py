# pyright: reportImplicitStringConcatenation=false

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api.config import load_database_settings

INSERT_CALL_SQL = """
INSERT INTO llm_call_records
    (id, scope, tenant_id, call_type, platform_attempt_id,
     job_requirement_parsing_task_id, configuration_version_id, input_snapshot_id,
     correlation_call_id, request_number, model, prompt_version_id, prompt_sha256,
     requirement_schema_version_id, requirement_schema_sha256, input_sources_summary,
     input_sha256, input_length, parameters, request_hash)
VALUES
    (:id, :scope, :tenant_id, :call_type, :platform_attempt_id,
     :parsing_task_id, :configuration_version_id, NULL, :correlation_call_id,
     :request_number, 'test/model', 'job-requirement-prompt-v1', repeat('a', 64),
     'job-requirement-schema-v1', repeat('b', 64),
     jsonb_build_object('kind', 'integration'), repeat('c', 64), 12,
     jsonb_build_object('temperature', 0), repeat('d', 64))
"""


@pytest.mark.anyio
@pytest.mark.integration
async def test_llm_call_scope_state_machine_rls_and_restricted_cleanup() -> None:  # noqa: PLR0915
    engine = create_async_engine(str(load_database_settings().database_url))
    attempt_id = uuid.uuid4()
    platform_call_id = uuid.uuid4()
    unknown_call_id = uuid.uuid4()
    tenant_call_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    parsing_task_id = uuid.uuid4()
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
                        "INSERT INTO llm_configuration_attempts "
                        "(id, status, candidate_snapshot, expected_current_version_id) "
                        "VALUES (:id, 'failed', "
                        "jsonb_build_object('model', 'test/model'), :current)"
                    ),
                    {"current": current_version_id, "id": attempt_id},
                )

                _ = await connection.execute(text("SET LOCAL ROLE relationship_platform_worker"))
                for call_id, request_number, correlation_call_id in (
                    (platform_call_id, 1, None),
                    (unknown_call_id, 2, platform_call_id),
                ):
                    _ = await connection.execute(
                        text(INSERT_CALL_SQL),
                        {
                            "call_type": "config_probe",
                            "configuration_version_id": None,
                            "correlation_call_id": correlation_call_id,
                            "id": call_id,
                            "parsing_task_id": None,
                            "platform_attempt_id": attempt_id,
                            "request_number": request_number,
                            "scope": "platform",
                            "tenant_id": None,
                        },
                    )
                _ = await connection.execute(
                    text(
                        "INSERT INTO llm_call_outcome_events "
                        "(call_id, sequence_number, scope, tenant_id, outcome) "
                        "VALUES (:id, 1, 'platform', NULL, 'succeeded')"
                    ),
                    {"id": platform_call_id},
                )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "INSERT INTO llm_call_outcome_events "
                                "(call_id, sequence_number, scope, tenant_id, outcome) "
                                "VALUES (:id, 2, 'platform', NULL, 'late_response')"
                            ),
                            {"id": platform_call_id},
                        )
                _ = await connection.execute(
                    text(
                        "INSERT INTO llm_call_outcome_events "
                        "(call_id, sequence_number, scope, tenant_id, outcome) "
                        "VALUES (:id, 1, 'platform', NULL, 'outcome_unknown'), "
                        "(:id, 2, 'platform', NULL, 'late_response')"
                    ),
                    {"id": unknown_call_id},
                )
                _ = await connection.execute(
                    text(
                        "INSERT INTO llm_call_metadata_events "
                        "(call_id, sequence_number, scope, tenant_id, status, source) "
                        "VALUES (:id, 1, 'platform', NULL, 'available', 'response')"
                    ),
                    {"id": platform_call_id},
                )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "INSERT INTO llm_call_metadata_events "
                                "(call_id, sequence_number, scope, tenant_id, status, source, "
                                "next_retry_at) VALUES "
                                "(:id, 2, 'platform', NULL, 'retry_scheduled', "
                                "'generation_api', now())"
                            ),
                            {"id": platform_call_id},
                        )
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "INSERT INTO llm_call_outcome_events "
                                "(call_id, sequence_number, scope, tenant_id, outcome) "
                                "VALUES (:id, 3, 'platform', NULL, 'late_response')"
                            ),
                            {"id": unknown_call_id},
                        )

                _ = await connection.execute(text("RESET ROLE"))
                _ = await connection.execute(text("SET LOCAL ROLE relationship_app"))
                _ = await connection.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                _ = await connection.execute(
                    text(INSERT_CALL_SQL),
                    {
                        "call_type": "job_requirement_parsing",
                        "configuration_version_id": current_version_id,
                        "correlation_call_id": None,
                        "id": tenant_call_id,
                        "parsing_task_id": parsing_task_id,
                        "platform_attempt_id": None,
                        "request_number": 1,
                        "scope": "tenant",
                        "tenant_id": tenant_id,
                    },
                )
                visible = (
                    await connection.execute(text("SELECT array_agg(id) FROM llm_call_records"))
                ).scalar_one()
                assert visible == [tenant_call_id]
                _ = await connection.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(other_tenant_id)},
                )
                assert (
                    await connection.execute(text("SELECT count(*) FROM llm_call_records"))
                ).scalar_one() == 0
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(INSERT_CALL_SQL),
                            {
                                "call_type": "job_requirement_parsing",
                                "configuration_version_id": current_version_id,
                                "correlation_call_id": None,
                                "id": uuid.uuid4(),
                                "parsing_task_id": uuid.uuid4(),
                                "platform_attempt_id": None,
                                "request_number": 1,
                                "scope": "tenant",
                                "tenant_id": None,
                            },
                        )
                _ = await connection.execute(
                    text("SELECT set_config('app.platform_admin', 'on', true)")
                )
                admin_visible = (
                    await connection.execute(
                        text(
                            "SELECT array_agg(id) FROM llm_call_records "
                            "WHERE id IN (:platform_id, :unknown_id, :tenant_id)"
                        ),
                        {
                            "platform_id": platform_call_id,
                            "tenant_id": tenant_call_id,
                            "unknown_id": unknown_call_id,
                        },
                    )
                ).scalar_one()
                assert set(admin_visible) == {platform_call_id, unknown_call_id, tenant_call_id}
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text("UPDATE llm_call_records SET model = 'changed' WHERE id = :id"),
                            {"id": platform_call_id},
                        )

                _ = await connection.execute(text("RESET ROLE"))
                _ = await connection.execute(text("SET LOCAL ROLE relationship_platform_worker"))
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(
                                "INSERT INTO llm_call_outcome_events "
                                "(call_id, sequence_number, scope, tenant_id, outcome) "
                                "VALUES (:id, 1, 'tenant', :tenant_id, 'failed')"
                            ),
                            {"id": platform_call_id, "tenant_id": tenant_id},
                        )
                now = datetime.now(UTC)
                for raw_id, call_id, expires_at in (
                    (uuid.uuid4(), platform_call_id, now - timedelta(seconds=1)),
                    (uuid.uuid4(), unknown_call_id, now + timedelta(days=1)),
                ):
                    _ = await connection.execute(
                        text(
                            "INSERT INTO llm_raw_responses "
                            "(id, call_id, response_sequence, scope, tenant_id, key_id, nonce, "
                            "ciphertext, http_status, response_headers, expires_at) VALUES "
                            "(:raw_id, :call_id, 1, 'platform', NULL, 'v1', "
                            "decode(repeat('00', 12), 'hex'), decode('00', 'hex'), 200, "
                            "jsonb_build_object(), :expires_at)"
                        ),
                        {"call_id": call_id, "expires_at": expires_at, "raw_id": raw_id},
                    )
                _ = await connection.execute(text("RESET ROLE"))
                _ = await connection.execute(text("SET LOCAL ROLE relationship_llm_maintenance"))
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(text("SELECT * FROM llm_raw_responses"))
                assert (
                    await connection.execute(text("SELECT cleanup_expired_llm_raw_responses(100)"))
                ).scalar_one() == 1
                _ = await connection.execute(text("RESET ROLE"))
                remaining = (
                    await connection.execute(
                        text(
                            "SELECT count(*) FROM llm_raw_responses "
                            "WHERE call_id IN (:platform_id, :unknown_id)"
                        ),
                        {"platform_id": platform_call_id, "unknown_id": unknown_call_id},
                    )
                ).scalar_one()
                assert remaining == 1
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
