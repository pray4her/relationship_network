"""Shared Compose-seam helpers: fake OpenRouter, ready LLM config, and job parsing."""

from __future__ import annotations

import asyncio
import socket
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Protocol, cast

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from relationship_network_api.config import AppSettings, PlatformLlmSettings
from relationship_network_api.db import (
    OUTBOX_DISPATCHER_DATABASE_ROLE,
    PLATFORM_WORKER_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.job_requirement_worker import (
    process_task,
    run_scheduled_operation,
    schedule_due_tasks,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.llm_configuration_worker import (
    process_attempt,
    schedule_due_attempts,
)
from relationship_network_api.llm_configuration_worker import (
    run_scheduled_operation as run_platform_scheduled_operation,
)
from relationship_network_api.platform_outbox_dispatcher import (
    acknowledge,
    acknowledge_tenant,
    claim_batch,
    claim_tenant_batch,
    release,
    release_tenant,
)

from .auth_helpers import PASSWORD, enable_mfa, register

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class TenantCleanup(Protocol):
    emails: list[str]
    tenant_ids: list[uuid.UUID]


TEST_RAW_RESPONSE_KEYS: Final = '{"local-v1":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}'
FAKE_API_KEY: Final = "fake-openrouter-key"
JOB_DESCRIPTION: Final = "需要海外华人，H 指数至少 30，研究人工智能。"  # noqa: RUF001
TERMINAL_TASK_STATUSES: Final = frozenset({"succeeded", "failed", "cancelled"})
TERMINAL_ATTEMPT_STATUSES: Final = frozenset({"succeeded", "failed", "cancelled", "conflicted"})


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def candidate_attempt_payload(
    *,
    model: str,
    expected_current_version_id: str,
    parsing_prompt: str = manifest.JOB_REQUIREMENT_PROMPT_V2.id,
) -> dict[str, object]:
    return {
        "call_bindings": {
            "job_requirement_parsing": {
                "prompt_version_id": parsing_prompt,
                "request_timeout_seconds": 180,
            },
            "search_interpretation": {
                "prompt_version_id": manifest.SEARCH_INTERPRETATION_PROMPT_V1.id,
                "request_timeout_seconds": 15,
            },
        },
        "expected_current_version_id": expected_current_version_id,
        "model": model,
    }


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class Pipeline:
    stack: TenantCleanup
    settings: AppSettings
    transport: ASGITransport
    admin: AsyncClient
    admin_email: str
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    admin_ready: bool = field(default=False)

    def platform_settings(self) -> PlatformLlmSettings:
        return PlatformLlmSettings(
            database_url=self.settings.database_url,
            openrouter_api_key=self.settings.openrouter_api_key,
            openrouter_base_url=self.settings.openrouter_base_url,
            openrouter_site_url=self.settings.openrouter_site_url,
            openrouter_site_name=self.settings.openrouter_site_name,
            llm_raw_response_keys=self.settings.llm_raw_response_keys,
            llm_raw_response_active_key_id=self.settings.llm_raw_response_active_key_id,
        )

    def client(self) -> AsyncClient:
        return AsyncClient(transport=self.transport, base_url="http://test")


async def ensure_admin(pipeline: Pipeline) -> AsyncClient:
    if not pipeline.admin_ready:
        registered = await register(pipeline.admin, email=pipeline.admin_email)
        assert registered["tenant"] is None
        _ = await enable_mfa(pipeline.admin)
        pipeline.admin_ready = True
    return pipeline.admin


async def finish_attempt(pipeline: Pipeline, attempt_id: uuid.UUID) -> dict[str, object]:
    admin = await ensure_admin(pipeline)
    last: dict[str, object] | None = None
    await process_attempt(attempt_id, settings=pipeline.platform_settings())
    for _ in range(6):
        finished = await admin.get(f"/admin/llm-configuration-attempts/{attempt_id}")
        assert finished.status_code == 200
        last = cast("dict[str, object]", finished.json())
        if str(last["status"]) in TERMINAL_ATTEMPT_STATUSES:
            return last
        if str(last["status"]) == "retry_scheduled":
            await asyncio.sleep(3)
            _ = await run_platform_scheduled_operation(schedule_due_attempts)
        if str(last["status"]) in {"queued", "retry_scheduled"}:
            await process_attempt(attempt_id, settings=pipeline.platform_settings())
            continue
        await asyncio.sleep(0.25)
    message = "configuration attempt did not reach a terminal status"
    raise AssertionError(message)


async def clear_active_attempt(pipeline: Pipeline) -> None:
    admin = await ensure_admin(pipeline)
    workspace = await admin.get("/admin/llm-configuration")
    assert workspace.status_code == 200
    active = workspace.json()["active_attempt"]
    if active is None:
        return
    attempt_id = uuid.UUID(cast("str", active["id"]))
    cancelled = await admin.post(f"/admin/llm-configuration-attempts/{attempt_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    _ = await finish_attempt(pipeline, attempt_id)


async def enable_ready_configuration(
    pipeline: Pipeline,
    *,
    model: str = "test/success",
    prompt_version_id: str = manifest.JOB_REQUIREMENT_PROMPT_V2.id,
) -> dict[str, object]:
    admin = await ensure_admin(pipeline)
    await clear_active_attempt(pipeline)
    workspace = await admin.get("/admin/llm-configuration")
    assert workspace.status_code == 200
    current = workspace.json()["current"]
    if current["model"] == model and current["prompt_version_id"] == prompt_version_id:
        return {"status": "succeeded", "id": current["id"]}
    created = await admin.post(
        "/admin/llm-configuration-attempts",
        json=candidate_attempt_payload(
            model=model,
            expected_current_version_id=current["id"],
            parsing_prompt=prompt_version_id,
        ),
    )
    assert created.status_code == 202, created.text
    attempt_id = uuid.UUID(created.json()["id"])
    await process_attempt(attempt_id, settings=pipeline.platform_settings())
    return await finish_attempt(pipeline, attempt_id)


async def register_tenant(pipeline: Pipeline, client: AsyncClient) -> uuid.UUID:
    email = f"itest-{uuid.uuid4().hex}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "解析租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    pipeline.stack.emails.append(email)
    pipeline.stack.tenant_ids.append(tenant_id)
    return tenant_id


async def create_job_with_description(client: AsyncClient) -> uuid.UUID:
    company = await client.post("/companies", json={"name": "解析企业"})
    assert company.status_code == 201
    job = await client.post(
        "/jobs",
        json={
            "company_id": company.json()["id"],
            "title": "研究人才负责人",
            "description": JOB_DESCRIPTION,
        },
    )
    assert job.status_code == 201
    return uuid.UUID(job.json()["id"])


async def start_parsing_task(
    client: AsyncClient,
    job_id: uuid.UUID,
    *,
    extra_sources: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    sources = [{"source_id": "job-description", "corrected_text": JOB_DESCRIPTION}]
    if extra_sources is not None:
        sources.extend(extra_sources)
    created = await client.post(
        f"/jobs/{job_id}/requirement-parsing-tasks",
        json={"idempotency_key": str(uuid.uuid4()), "sources": sources},
    )
    assert created.status_code == 202, created.text
    return cast("dict[str, object]", created.json())


async def process_parsing_task(
    pipeline: Pipeline,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> None:
    await process_task(tenant_id, task_id, settings=pipeline.settings)


async def divert_platform_outbox(pipeline: Pipeline, *, aggregate_id: uuid.UUID) -> None:
    """Ack the matching platform Outbox row so the live dispatcher does not steal it."""
    engine = create_engine_from_settings(
        pipeline.settings,
        database_role=OUTBOX_DISPATCHER_DATABASE_ROLE,
    )
    try:
        factory = create_session_factory(engine)
        claimant = uuid.uuid4()
        async with factory() as session:
            events = await claim_batch(session, claimant=claimant)
        for event in events:
            if event.aggregate_id == aggregate_id:
                await acknowledge(factory, event_id=event.id, claimant=claimant)
            else:
                await release(
                    factory,
                    event_id=event.id,
                    claimant=claimant,
                    error_text="integration test diverted another event",
                )
    finally:
        await engine.dispose()


async def divert_tenant_outbox(
    pipeline: Pipeline,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> None:
    """Ack the matching tenant Outbox row so the live dispatcher does not steal it."""
    engine = create_engine_from_settings(
        pipeline.settings,
        database_role=OUTBOX_DISPATCHER_DATABASE_ROLE,
    )
    try:
        factory = create_session_factory(engine)
        claimant = uuid.uuid4()
        async with factory() as session:
            events = await claim_tenant_batch(session, claimant=claimant)
        for event in events:
            if event.task_id == task_id and event.tenant_id == tenant_id:
                await acknowledge_tenant(factory, event_id=event.id, claimant=claimant)
            else:
                await release_tenant(
                    factory,
                    event_id=event.id,
                    claimant=claimant,
                    error_text="integration test diverted another event",
                )
    finally:
        await engine.dispose()


async def process_until_terminal(  # noqa: PLR0913
    pipeline: Pipeline,
    client: AsyncClient,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    attempts: int = 40,
) -> dict[str, object]:
    last: dict[str, object] | None = None
    await process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
    for _ in range(attempts):
        workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
        assert workspace.status_code == 200
        last = cast("dict[str, object]", workspace.json())
        task = last.get("task")
        if not isinstance(task, dict):
            await asyncio.sleep(0.25)
            continue
        status = task.get("status")
        if not isinstance(status, str):
            await asyncio.sleep(0.25)
            continue
        if status in TERMINAL_TASK_STATUSES:
            return last
        if status == "retry_scheduled":
            await asyncio.sleep(3)
            _ = await run_scheduled_operation(schedule_due_tasks)
        if status in {"queued", "retry_scheduled"}:
            await process_parsing_task(pipeline, tenant_id=tenant_id, task_id=task_id)
            continue
        await asyncio.sleep(0.25)
    message = "parsing task did not reach a terminal status"
    raise AssertionError(message)


INSERT_CONFIGURATION_VERSION_SQL: Final = """
INSERT INTO llm_configuration_versions
    (id, version_number, provider, model, prompt_version_id,
     requirement_schema_version_id, temperature, max_output_tokens,
     request_timeout_seconds, privacy_routing, source)
VALUES
    (:id, :version_number, 'openrouter', :model, :prompt_id, :schema_id,
     0, 8192, 180,
     jsonb_build_object('zdr', true, 'data_collection', 'deny',
                        'require_parameters', true), 'probe')
"""


async def activate_current_model(pipeline: Pipeline, *, model: str) -> uuid.UUID:
    """Point current configuration at a model without running a new probe."""
    version_id = uuid.uuid4()
    engine = create_engine_from_settings(
        pipeline.settings,
        database_role=PLATFORM_WORKER_DATABASE_ROLE,
    )
    try:
        async with engine.begin() as connection:
            current_id = (
                await connection.execute(
                    text("SELECT version_id FROM llm_configuration_current WHERE singleton")
                )
            ).scalar_one()
            next_number_sql = (
                "SELECT coalesce(max(version_number), 0) + 1 FROM llm_configuration_versions"
            )
            version_number = (await connection.execute(text(next_number_sql))).scalar_one()
            _ = await connection.execute(
                text(INSERT_CONFIGURATION_VERSION_SQL),
                {
                    "id": version_id,
                    "model": model,
                    "prompt_id": manifest.JOB_REQUIREMENT_PROMPT_V2.id,
                    "schema_id": manifest.JOB_REQUIREMENT_SCHEMA_V2.id,
                    "version_number": version_number,
                },
            )
            activated = (
                await connection.execute(
                    text("SELECT activate_llm_configuration_version(:current_id, :new_id)"),
                    {"current_id": current_id, "new_id": version_id},
                )
            ).scalar_one()
            assert activated is True
    finally:
        await engine.dispose()
    return version_id


async def snapshot_current_version(settings: AppSettings) -> uuid.UUID:
    engine = create_engine_from_settings(
        settings,
        database_role=PLATFORM_WORKER_DATABASE_ROLE,
    )
    try:
        async with engine.connect() as connection:
            current_id = (
                await connection.execute(
                    text("SELECT version_id FROM llm_configuration_current WHERE singleton")
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    return uuid.UUID(str(current_id))


async def restore_current_version(settings: AppSettings, version_id: uuid.UUID) -> None:
    engine = create_engine_from_settings(
        settings,
        database_role=PLATFORM_WORKER_DATABASE_ROLE,
    )
    try:
        async with engine.begin() as connection:
            current_id = (
                await connection.execute(
                    text("SELECT version_id FROM llm_configuration_current WHERE singleton")
                )
            ).scalar_one()
            if current_id == version_id:
                return
            activated = (
                await connection.execute(
                    text("SELECT activate_llm_configuration_version(:current_id, :new_id)"),
                    {"current_id": current_id, "new_id": version_id},
                )
            ).scalar_one()
            if activated is not True:
                message = "failed to restore LLM current configuration"
                raise RuntimeError(message)
    finally:
        await engine.dispose()


async def collect_sse_events(
    client: AsyncClient,
    *,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    last_event_id: str = "0",
) -> list[str]:
    events: list[str] = []
    response = await client.get(
        f"/jobs/{job_id}/requirement-parsing-tasks/{task_id}/events",
        headers={"Last-Event-ID": last_event_id},
        timeout=10.0,
    )
    assert response.status_code == 200, response.text
    for line in response.text.splitlines():
        if line.startswith("event:"):
            events.append(line.split(":", 1)[1].strip())
        if events and events[-1] in TERMINAL_TASK_STATUSES:
            break
    return events
