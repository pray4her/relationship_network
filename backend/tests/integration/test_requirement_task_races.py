from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import func, select, update

from relationship_network_api.fake_openrouter import timing
from relationship_network_api.job_requirement_worker import (
    claim_task,
    recover_expired_task_leases,
    run_scheduled_operation,
)
from relationship_network_api.models import (
    JobRequirementDraft,
    JobRequirementParsingTask,
    LlmCallOutcomeEvent,
    LlmCallRecord,
)
from relationship_network_api.tenant_context import set_tenant_context

from .openrouter_pipeline import (
    Pipeline,
    collect_sse_events,
    create_job_with_description,
    divert_tenant_outbox,
    enable_ready_configuration,
    mapping,
    process_parsing_task,
    process_until_terminal,
    register_tenant,
    start_parsing_task,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _record_unknown_outcome_and_expire_lease(
    pipeline: Pipeline,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> None:
    recorded: tuple[uuid.UUID, str, uuid.UUID | None] | None = None
    for _ in range(50):
        async with pipeline.session_factory() as session:
            await set_tenant_context(session, tenant_id)
            call = (
                await session.execute(
                    select(LlmCallRecord).where(
                        LlmCallRecord.job_requirement_parsing_task_id == task_id
                    )
                )
            ).scalar_one_or_none()
            if call is not None:
                recorded = (call.id, call.scope, call.tenant_id)
        if recorded is not None:
            break
        await asyncio.sleep(0.05)
    if recorded is None:
        message = "call record was not created"
        raise AssertionError(message)
    call_id, call_scope, call_tenant_id = recorded
    async with pipeline.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        session.add(
            LlmCallOutcomeEvent(
                call_id=call_id,
                scope=call_scope,
                tenant_id=call_tenant_id,
                sequence_number=1,
                outcome="outcome_unknown",
                category="timeout",
            )
        )
        _ = await session.execute(
            update(JobRequirementParsingTask)
            .where(JobRequirementParsingTask.id == task_id)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    recovered = await run_scheduled_operation(recover_expired_task_leases)
    assert recovered >= 1
    await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)


async def _wait_task_status(
    client: AsyncClient,
    *,
    job_id: uuid.UUID,
    expected: set[str],
) -> str:
    for _ in range(50):
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        task = workspace.json()["task"]
        if task is not None and str(task["status"]) in expected:
            return str(task["status"])
        await asyncio.sleep(0.1)
    message = f"task did not reach {sorted(expected)}"
    raise AssertionError(message)


@pytest.mark.anyio
@pytest.mark.integration
async def test_duplicate_delivery_does_not_create_two_drafts(pipeline: Pipeline) -> None:
    _ = await enable_ready_configuration(pipeline)
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        _ = await asyncio.gather(
            process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id),
            process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id),
        )
        await process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.json()["task"]["status"] == "succeeded"
        assert workspace.json()["draft"]["status"] == "editable"

    async with pipeline.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        drafts = (
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
    assert int(drafts) == 1
    assert int(calls) == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_expired_lease_requeues_the_same_task(pipeline: Pipeline) -> None:
    _ = await enable_ready_configuration(pipeline)
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        claim = await claim_task(
            pipeline.session_factory,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        assert claim is not None
        async with pipeline.session_factory() as session:
            await set_tenant_context(session, tenant_id)
            _ = await session.execute(
                update(JobRequirementParsingTask)
                .where(JobRequirementParsingTask.id == task_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()
        recovered = await run_scheduled_operation(recover_expired_task_leases)
        assert recovered >= 1
        await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.json()["task"]["status"] == "queued"
        finished = await process_until_terminal(
            pipeline,
            client,
            tenant_id=tenant_id,
            job_id=job_id,
            task_id=task_id,
        )
        assert mapping(finished["task"])["status"] == "succeeded"
        assert mapping(finished["draft"])["status"] == "editable"


@pytest.mark.anyio
@pytest.mark.integration
async def test_cancel_during_delayed_success_does_not_write_a_draft(
    pipeline: Pipeline,
) -> None:
    timing.delay_seconds = 0.05
    _ = await enable_ready_configuration(pipeline, model="test/delayed-success")
    timing.delay_seconds = 1.5
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)
        worker = asyncio.create_task(
            process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
        )
        try:
            _ = await _wait_task_status(client, job_id=job_id, expected={"running"})
            cancelled = await client.post(
                f"/jobs/{job_id}/requirement-parsing-tasks/{task_id}/cancel"
            )
            assert cancelled.status_code == 200, cancelled.text
            await worker
        finally:
            if not worker.done():
                _ = worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.json()["task"]["status"] == "cancelled"
        assert workspace.json()["draft"] is None


@pytest.mark.anyio
@pytest.mark.integration
async def test_archive_during_delayed_success_does_not_write_a_draft(
    pipeline: Pipeline,
) -> None:
    timing.delay_seconds = 0.05
    _ = await enable_ready_configuration(pipeline, model="test/delayed-success")
    timing.delay_seconds = 1.5
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)
        worker = asyncio.create_task(
            process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
        )
        try:
            _ = await _wait_task_status(client, job_id=job_id, expected={"running"})
            archived = await client.post(f"/jobs/{job_id}/archive")
            assert archived.status_code == 200, archived.text
            await worker
        finally:
            if not worker.done():
                _ = worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.json()["task"]["status"] in {"cancelled", "failed"}
        assert workspace.json()["draft"] is None


@pytest.mark.anyio
@pytest.mark.integration
async def test_late_response_after_outcome_unknown_does_not_write_a_draft(
    pipeline: Pipeline,
) -> None:
    timing.delay_seconds = 0.05
    _ = await enable_ready_configuration(pipeline, model="test/delayed-success")
    timing.delay_seconds = 1.5
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
        task = await start_parsing_task(client, job_id)
        task_id = uuid.UUID(cast("str", task["id"]))
        await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)
        worker = asyncio.create_task(
            process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
        )
        try:
            _ = await _wait_task_status(client, job_id=job_id, expected={"running"})
            await _record_unknown_outcome_and_expire_lease(
                pipeline,
                tenant_id=tenant_id,
                task_id=task_id,
            )
            await worker
        finally:
            if not worker.done():
                _ = worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
        async with pipeline.session_factory() as session:
            await set_tenant_context(session, tenant_id)
            outcomes = list(
                (
                    await session.execute(
                        select(LlmCallOutcomeEvent.outcome).order_by(
                            LlmCallOutcomeEvent.sequence_number
                        )
                    )
                ).scalars()
            )
            drafts = (
                await session.execute(
                    select(func.count())
                    .select_from(JobRequirementDraft)
                    .where(JobRequirementDraft.tenant_id == tenant_id)
                )
            ).scalar_one()
        assert "outcome_unknown" in outcomes or "late_response" in outcomes
        assert int(drafts) == 0
        await divert_tenant_outbox(pipeline, tenant_id=tenant_id, task_id=task_id)
        timing.delay_seconds = 0.05
        finished = await process_until_terminal(
            pipeline,
            client,
            tenant_id=tenant_id,
            job_id=job_id,
            task_id=task_id,
        )
        assert mapping(finished["task"])["status"] == "succeeded"
        assert mapping(finished["draft"])["status"] == "editable"


@pytest.mark.anyio
@pytest.mark.integration
async def test_sse_replays_from_last_event_id_after_notify_loss(
    pipeline: Pipeline,
) -> None:
    _ = await enable_ready_configuration(pipeline)
    async with pipeline.client() as client:
        tenant_id = await register_tenant(pipeline, client)
        job_id = await create_job_with_description(client)
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
        replayed = await collect_sse_events(
            client,
            job_id=job_id,
            task_id=task_id,
            last_event_id="0",
        )
        assert replayed[-1] == "succeeded"
        assert "queued" in replayed or "running" in replayed
