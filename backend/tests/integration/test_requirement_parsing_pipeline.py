from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy import func, select

from relationship_network_api.models import JobRequirementDraft, LlmCallRecord
from relationship_network_api.tenant_context import set_tenant_context

from .openrouter_pipeline import (
    Pipeline,
    activate_current_model,
    collect_sse_events,
    create_job_with_description,
    enable_ready_configuration,
    mapping,
    process_until_terminal,
    register_tenant,
    start_parsing_task,
)


@pytest.mark.anyio
@pytest.mark.integration
async def test_authenticated_parsing_creates_exactly_one_draft_and_replays_sse(
    pipeline: Pipeline,
) -> None:
    attempt = await enable_ready_configuration(pipeline)
    assert attempt["status"] == "succeeded"

    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.status_code == 200
        assert workspace.json()["configuration_ready"] is True

        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        finished = await process_until_terminal(
            pipeline,
            client,
            tenant_id=tenant_id,
            job_id=job_id,
            task_id=task_id,
        )
        assert mapping(finished["task"])["status"] == "succeeded"
        draft = mapping(finished["draft"])
        assert draft["status"] == "editable"
        draft_id = draft["id"]

        events = await collect_sse_events(client, job_id=job_id, task_id=task_id)
        assert "queued" in events or "running" in events
        assert events[-1] == "succeeded"

        confirmed = await client.post(
            f"/jobs/{job_id}/requirement-drafts/{draft_id}/confirm",
            json={"expected_revision": draft["revision"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["version"]["version_number"] == 1
        copied = await client.post(f"/jobs/{job_id}/requirement-versions/copy-current")
        assert copied.status_code == 200, copied.text
        assert copied.json()["status"] == "editable"

    async with pipeline.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        editable = (
            await session.execute(
                select(func.count())
                .select_from(JobRequirementDraft)
                .where(
                    JobRequirementDraft.tenant_id == tenant_id,
                    JobRequirementDraft.status == "editable",
                )
            )
        ).scalar_one()
        calls = (
            await session.execute(
                select(func.count())
                .select_from(LlmCallRecord)
                .where(LlmCallRecord.tenant_id == tenant_id)
            )
        ).scalar_one()
    assert int(editable) == 1
    assert int(calls) == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_invalid_structure_fails_without_creating_a_draft(pipeline: Pipeline) -> None:
    attempt = await enable_ready_configuration(pipeline)
    assert attempt["status"] == "succeeded"
    _ = await activate_current_model(pipeline, model="test/invalid-structure")

    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        finished = await process_until_terminal(
            pipeline,
            client,
            tenant_id=tenant_id,
            job_id=job_id,
            task_id=uuid.UUID(cast("str", task["id"])),
        )
        assert mapping(finished["task"])["status"] == "failed"
        assert finished["draft"] is None

    async with pipeline.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        drafts = (
            await session.execute(
                select(func.count())
                .select_from(JobRequirementDraft)
                .where(JobRequirementDraft.tenant_id == tenant_id)
            )
        ).scalar_one()
    assert int(drafts) == 0
