import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from relationship_network_api.config import load_database_settings

CURRENT_ID = "00000000-0000-0000-0000-000000000110"
INSERT_ATTEMPT_SQL = """
INSERT INTO llm_configuration_attempts
    (id, status, candidate_snapshot, expected_current_version_id)
VALUES (:id, 'queued', jsonb_build_object('model', 'test/model'), :current_id)
"""
INSERT_EMPTY_ATTEMPT_SQL = """
INSERT INTO llm_configuration_attempts
    (id, status, candidate_snapshot, expected_current_version_id)
VALUES (:id, 'queued', jsonb_build_object(), :current_id)
"""
INSERT_EVENT_SQL = """
INSERT INTO llm_configuration_attempt_events
    (attempt_id, sequence_number, event_type, payload)
VALUES (:id, :sequence, 'queued', jsonb_build_object())
"""
INSERT_VERSION_SQL = """
INSERT INTO llm_configuration_versions
    (id, version_number, provider, model, prompt_version_id,
     requirement_schema_version_id, temperature, max_output_tokens,
     request_timeout_seconds, privacy_routing, source)
VALUES
    (:id, 2, 'openrouter', 'test/model', 'job-requirement-prompt-v1',
     'job-requirement-schema-v1', 0, 8192, 180,
     jsonb_build_object('zdr', true, 'data_collection', 'deny',
                        'require_parameters', true), 'probe')
"""


@pytest.mark.anyio
@pytest.mark.integration
async def test_llm_configuration_database_invariants_and_restricted_roles() -> None:
    engine = create_async_engine(str(load_database_settings().database_url))
    attempt_id = uuid.uuid4()
    second_attempt_id = uuid.uuid4()
    version_id = uuid.uuid4()
    claimant_id = uuid.uuid4()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                _ = await connection.execute(text("SET LOCAL ROLE relationship_app"))
                _ = await connection.execute(
                    text(INSERT_ATTEMPT_SQL),
                    {"current_id": CURRENT_ID, "id": attempt_id},
                )
                _ = await connection.execute(
                    text(INSERT_EVENT_SQL),
                    {"id": attempt_id, "sequence": 1},
                )

                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(INSERT_EVENT_SQL),
                            {"id": attempt_id, "sequence": 3},
                        )

                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text(INSERT_EMPTY_ATTEMPT_SQL),
                            {"current_id": CURRENT_ID, "id": second_attempt_id},
                        )
            finally:
                await transaction.rollback()

            transaction = await connection.begin()
            try:
                _ = await connection.execute(text("SET LOCAL ROLE relationship_platform_worker"))
                _ = await connection.execute(
                    text(INSERT_VERSION_SQL),
                    {"id": version_id},
                )
                activated = (
                    await connection.execute(
                        text("SELECT activate_llm_configuration_version(:current_id, :new_id)"),
                        {"current_id": CURRENT_ID, "new_id": version_id},
                    )
                ).scalar_one()
                pointer = (
                    await connection.execute(
                        text("SELECT version_id FROM llm_configuration_current WHERE singleton")
                    )
                ).scalar_one()
                assert activated is True
                assert pointer == version_id
            finally:
                await transaction.rollback()

            transaction = await connection.begin()
            try:
                _ = await connection.execute(text("SET LOCAL ROLE relationship_outbox_dispatcher"))
                claimed = (
                    await connection.execute(
                        text("SELECT count(*) FROM claim_platform_outbox_batch(:claimant, 25, 30)"),
                        {"claimant": claimant_id},
                    )
                ).scalar_one()
                assert claimed == 0
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        _ = await connection.execute(
                            text("SELECT count(*) FROM llm_configuration_attempts")
                        )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
