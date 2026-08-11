"""Lease-based, retryable tenant Worker for job requirement parsing tasks."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, final

import anyio
from sqlalchemy import func, select, text

from relationship_network_api import job_requirement_service as service
from relationship_network_api import llm_call_audit_service as call_audit
from relationship_network_api import tenant_audit_service, tenant_context
from relationship_network_api.config import AppSettings, load_app_settings, load_database_settings
from relationship_network_api.db import (
    REQUIREMENT_SCHEDULER_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.durable_task import (
    HEARTBEAT_SECONDS,
    MAX_EXTERNAL_CALLS,
    MAX_STRUCTURED_INVALID_CALLS,
    lease_seconds_for_timeout,
    retry_delay_seconds,
)
from relationship_network_api.job_requirement_validation import (
    RequirementResultValidationError,
    validate_requirement_result,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    Job,
    JobRequirementDraft,
    JobRequirementInputSnapshot,
    JobRequirementInputSource,
    JobRequirementParsingTask,
    JobRequirementSchemaVersion,
    LlmCallOutcomeEvent,
    LlmCallRecord,
    LlmConfigurationVersion,
    PromptVersion,
    Tenant,
)
from relationship_network_api.openrouter import (
    CandidateConfiguration,
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

TENANT_INVALID_OUTPUT: Final = "requirement_output_invalid"
TENANT_TEMPORARY_FAILURE: Final = "requirement_generation_unavailable"
TENANT_CONFIGURATION_FAILURE: Final = "requirement_configuration_unavailable"
TENANT_JOB_ARCHIVED: Final = "job_archived"
MAX_RUNNING_PER_TENANT: Final = 2
SLOT_RETRY_SECONDS: Final = 5


@final
@dataclass(frozen=True)
class ClaimedTask:
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    lease_token: uuid.UUID
    lease_seconds: int


@final
@dataclass(frozen=True)
class PreparedTask:
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    job_id: uuid.UUID
    snapshot_id: uuid.UUID
    call_id: uuid.UUID
    lease_token: uuid.UUID
    actor_user_id: uuid.UUID | None
    candidate: CandidateConfiguration
    prompt: str
    schema_id: str
    schema: dict[str, object]
    sources: list[dict[str, str]]
    source_texts: dict[str, str]


async def process_task(
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    *,
    settings: AppSettings | None = None,
) -> None:
    """Idempotently process one at-least-once Celery delivery."""
    resolved = settings or load_app_settings()
    engine = create_engine_from_settings(resolved)
    factory = create_session_factory(engine)
    try:
        claim = await claim_task(factory, tenant_id=tenant_id, task_id=task_id)
        if claim is None:
            return
        if resolved.openrouter_api_key is None:
            await fail_without_call(
                factory,
                claim=claim,
                error_code=TENANT_CONFIGURATION_FAILURE,
            )
            return
        try:
            key_ring = call_audit.RawResponseKeyRing.parse(
                resolved.llm_raw_response_keys.get_secret_value(),
                resolved.llm_raw_response_active_key_id,
            )
            _ = key_ring.require_active_key()
        except call_audit.RawResponseKeyConfigurationError:
            await fail_without_call(
                factory,
                claim=claim,
                error_code=TENANT_CONFIGURATION_FAILURE,
            )
            return
        prepared = await prepare_call(factory, claim=claim)
        if prepared is None:
            return
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(
                api_key=resolved.openrouter_api_key.get_secret_value(),
                base_url=resolved.openrouter_base_url,
                site_url=resolved.openrouter_site_url,
                site_name=resolved.openrouter_site_name,
            )
        )
        stop_heartbeat = anyio.Event()
        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(heartbeat_loop, factory, claim, stop_heartbeat)
            started_ns = time.monotonic_ns()
            try:
                result = await adapter.generate_requirement(
                    prepared.candidate,
                    system_prompt=prepared.prompt,
                    schema=prepared.schema,
                    sources=prepared.sources,
                )
            except OpenRouterAdapterError as error:
                duration_ms = max((time.monotonic_ns() - started_ns) // 1_000_000, 0)
                stop_heartbeat.set()
                persisted = await call_audit.persist_call_response(
                    factory,
                    call_id=prepared.call_id,
                    key_ring=key_ring,
                    requested_outcome="outcome_unknown" if error.outcome_unknown else "failed",
                    category=error.category,
                    exchange=error.exchange,
                    result=None,
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                )
                if not persisted.is_late_response:
                    await handle_failure(
                        factory,
                        prepared=prepared,
                        category=error.category,
                        retryable=error.retryable,
                        outcome_unknown=error.outcome_unknown,
                        retry_after_seconds=error.retry_after_seconds,
                        structured_invalid=False,
                    )
                return
            duration_ms = max((time.monotonic_ns() - started_ns) // 1_000_000, 0)
            try:
                validated = validate_requirement_result(
                    result.content,
                    schema=prepared.schema,
                    asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
                    source_texts=prepared.source_texts,
                )
            except RequirementResultValidationError as error:
                stop_heartbeat.set()
                persisted = await call_audit.persist_call_response(
                    factory,
                    call_id=prepared.call_id,
                    key_ring=key_ring,
                    requested_outcome="failed",
                    category=error.category,
                    exchange=result.exchange,
                    result=None,
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                )
                if not persisted.is_late_response:
                    await handle_failure(
                        factory,
                        prepared=prepared,
                        category=error.category,
                        retryable=True,
                        outcome_unknown=False,
                        retry_after_seconds=None,
                        structured_invalid=True,
                    )
                return
            stop_heartbeat.set()
            persisted = await call_audit.persist_call_response(
                factory,
                call_id=prepared.call_id,
                key_ring=key_ring,
                requested_outcome="succeeded",
                category="",
                exchange=result.exchange,
                result=result,
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )
            if not persisted.is_late_response:
                await complete_task(factory, prepared=prepared, result=validated)
    finally:
        await engine.dispose()


async def claim_task(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> ClaimedTask | None:
    async with session_factory() as session, session.begin():
        await tenant_context.set_tenant_context(session, tenant_id)
        _ = (
            await session.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
        ).scalar_one_or_none()
        task = await _locked_task(session, tenant_id=tenant_id, task_id=task_id)
        if task is None or task.status != "queued":
            return None
        active_slots = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(JobRequirementParsingTask)
                    .where(
                        JobRequirementParsingTask.tenant_id == tenant_id,
                        JobRequirementParsingTask.status.in_(("running", "cancel_requested")),
                        JobRequirementParsingTask.id != task_id,
                    )
                )
            ).scalar_one()
        )
        if active_slots >= MAX_RUNNING_PER_TENANT:
            _ = await session.execute(
                text(
                    "SELECT enqueue_delayed_requirement_task(:task_id, :tenant_id, :delay_seconds)"
                ),
                {
                    "delay_seconds": SLOT_RETRY_SECONDS,
                    "task_id": task_id,
                    "tenant_id": tenant_id,
                },
            )
            return None
        configuration = (
            await session.execute(
                select(LlmConfigurationVersion).where(
                    LlmConfigurationVersion.id == task.configuration_version_id
                )
            )
        ).scalar_one()
        lease_seconds = lease_seconds_for_timeout(configuration.request_timeout_seconds)
        token = uuid.uuid4()
        now = datetime.now(UTC)
        task.status = "running"
        task.error_code = None
        task.lease_token = token
        task.lease_expires_at = now + timedelta(seconds=lease_seconds)
        task.last_heartbeat_at = now
        task.next_attempt_at = None
        if task.started_at is None:
            task.started_at = now
        _ = await service.append_task_event(session, task=task, payload={})
        return ClaimedTask(
            tenant_id=tenant_id,
            task_id=task_id,
            lease_token=token,
            lease_seconds=lease_seconds,
        )


async def prepare_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedTask,
) -> PreparedTask | None:
    async with session_factory() as session, session.begin():
        await tenant_context.set_tenant_context(session, claim.tenant_id)
        task = await _locked_task(
            session,
            tenant_id=claim.tenant_id,
            task_id=claim.task_id,
        )
        if not _holds_running_lease(task, claim.lease_token):
            return None
        if task is None:
            return None
        snapshot = (
            await session.execute(
                select(JobRequirementInputSnapshot).where(
                    JobRequirementInputSnapshot.id == task.input_snapshot_id,
                    JobRequirementInputSnapshot.tenant_id == claim.tenant_id,
                )
            )
        ).scalar_one()
        configuration = (
            await session.execute(
                select(LlmConfigurationVersion).where(
                    LlmConfigurationVersion.id == task.configuration_version_id
                )
            )
        ).scalar_one()
        prompt = (
            await session.execute(
                select(PromptVersion).where(PromptVersion.id == configuration.prompt_version_id)
            )
        ).scalar_one()
        schema = (
            await session.execute(
                select(JobRequirementSchemaVersion).where(
                    JobRequirementSchemaVersion.id == configuration.requirement_schema_version_id
                )
            )
        ).scalar_one()
        if not _assets_match(prompt=prompt, schema=schema):
            await _fail_locked_task(
                session,
                task=task,
                error_code=TENANT_CONFIGURATION_FAILURE,
            )
            return None
        request_number = task.external_call_count + 1
        if request_number > MAX_EXTERNAL_CALLS:
            await _fail_locked_task(
                session,
                task=task,
                error_code=TENANT_TEMPORARY_FAILURE,
            )
            return None
        source_rows = list(
            (
                await session.execute(
                    select(JobRequirementInputSource)
                    .where(
                        JobRequirementInputSource.snapshot_id == snapshot.id,
                        JobRequirementInputSource.tenant_id == claim.tenant_id,
                    )
                    .order_by(JobRequirementInputSource.position)
                )
            )
            .scalars()
            .all()
        )
        candidate = CandidateConfiguration(
            model=configuration.model,
            prompt_version_id=configuration.prompt_version_id,
            temperature=float(configuration.temperature),
            max_output_tokens=configuration.max_output_tokens,
            request_timeout_seconds=configuration.request_timeout_seconds,
            input_character_limit=configuration.input_character_limit,
        )
        sources = [
            {"content": source.sent_text, "source_id": source.source_id} for source in source_rows
        ]
        request_payload = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="not-persisted")
        ).build_requirement_payload(
            candidate,
            system_prompt=prompt.content,
            schema=schema.schema_json,
            sources=sources,
        )
        request_hash = hashlib.sha256(
            json.dumps(
                request_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        previous_call_id = await _previous_unknown_call_id(
            session,
            task_id=task.id,
            request_number=request_number,
        )
        call = LlmCallRecord(
            id=uuid.uuid4(),
            scope="tenant",
            tenant_id=claim.tenant_id,
            call_type="job_requirement_parsing",
            platform_attempt_id=None,
            job_requirement_parsing_task_id=task.id,
            configuration_version_id=configuration.id,
            input_snapshot_id=snapshot.id,
            correlation_call_id=previous_call_id,
            request_number=request_number,
            model=configuration.model,
            prompt_version_id=prompt.id,
            prompt_sha256=prompt.sha256,
            requirement_schema_version_id=schema.id,
            requirement_schema_sha256=schema.sha256,
            input_sources_summary={
                "sources": [
                    {
                        "characters": source.unicode_characters,
                        "position": source.position,
                        "sent_sha256": source.sent_sha256,
                        "source_id": source.source_id,
                    }
                    for source in source_rows
                ]
            },
            input_sha256=snapshot.content_sha256,
            input_length=snapshot.total_characters,
            parameters={
                "max_output_tokens": configuration.max_output_tokens,
                "request_timeout_seconds": configuration.request_timeout_seconds,
                "temperature": float(configuration.temperature),
            },
            request_hash=request_hash,
        )
        task.external_call_count = request_number
        session.add(call)
        await session.flush()
        return PreparedTask(
            tenant_id=claim.tenant_id,
            task_id=task.id,
            job_id=task.job_id,
            snapshot_id=snapshot.id,
            call_id=call.id,
            lease_token=claim.lease_token,
            actor_user_id=task.created_by,
            candidate=candidate,
            prompt=prompt.content,
            schema_id=schema.id,
            schema=schema.schema_json,
            sources=sources,
            source_texts={source.source_id: source.sent_text for source in source_rows},
        )


async def heartbeat_loop(
    session_factory: async_sessionmaker[AsyncSession],
    claim: ClaimedTask,
    stop: anyio.Event,
) -> None:
    while True:
        with anyio.move_on_after(HEARTBEAT_SECONDS):
            await stop.wait()
        if stop.is_set():
            return
        async with session_factory() as session, session.begin():
            await tenant_context.set_tenant_context(session, claim.tenant_id)
            task = await _locked_task(
                session,
                tenant_id=claim.tenant_id,
                task_id=claim.task_id,
            )
            if not _holds_active_lease(task, claim.lease_token):
                return
            if task is None:
                return
            now = datetime.now(UTC)
            task.last_heartbeat_at = now
            task.lease_expires_at = now + timedelta(seconds=claim.lease_seconds)


async def handle_failure(  # noqa: PLR0913
    session_factory: async_sessionmaker[AsyncSession],
    *,
    prepared: PreparedTask,
    category: str,
    retryable: bool,
    outcome_unknown: bool,
    retry_after_seconds: int | None,
    structured_invalid: bool,
) -> None:
    async with session_factory() as session, session.begin():
        await tenant_context.set_tenant_context(session, prepared.tenant_id)
        task = await _locked_task(
            session,
            tenant_id=prepared.tenant_id,
            task_id=prepared.task_id,
        )
        if task is None:
            return
        if task.status == "cancel_requested" and task.lease_token == prepared.lease_token:
            await _cancel_locked_task(session, task=task)
            return
        if not _holds_running_lease(task, prepared.lease_token):
            return
        if structured_invalid:
            task.structured_invalid_count += 1
        can_retry = (
            (retryable or outcome_unknown)
            and task.external_call_count < MAX_EXTERNAL_CALLS
            and (
                not structured_invalid
                or task.structured_invalid_count < MAX_STRUCTURED_INVALID_CALLS
            )
        )
        error_code = (
            TENANT_INVALID_OUTPUT
            if structured_invalid
            else _tenant_error(category=category, retryable=can_retry)
        )
        task.error_code = error_code
        if can_retry:
            delay_seconds = retry_after_seconds
            if delay_seconds is None:
                delay_seconds = retry_delay_seconds(task.external_call_count)
            next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            task.status = "retry_scheduled"
            task.next_attempt_at = next_attempt_at
            _clear_lease(task)
            _ = await service.append_task_event(
                session,
                task=task,
                payload={
                    "error_code": error_code,
                    "next_attempt_at": next_attempt_at.isoformat(),
                    "retryable": True,
                },
            )
            return
        task.status = "failed"
        task.completed_at = datetime.now(UTC)
        task.next_attempt_at = None
        _clear_lease(task)
        _ = await service.append_task_event(
            session,
            task=task,
            payload={"error_code": error_code, "retryable": False},
        )
        _record_failure_audit(session, task=task, error_code=error_code)


async def complete_task(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    prepared: PreparedTask,
    result: dict[str, object],
) -> None:
    async with session_factory() as session, session.begin():
        await tenant_context.set_tenant_context(session, prepared.tenant_id)
        job = (
            await session.execute(
                select(Job)
                .where(Job.id == prepared.job_id, Job.tenant_id == prepared.tenant_id)
                .with_for_update()
            )
        ).scalar_one()
        task = await _locked_task(
            session,
            tenant_id=prepared.tenant_id,
            task_id=prepared.task_id,
        )
        if task is None:
            return
        if task.status == "cancel_requested" and task.lease_token == prepared.lease_token:
            await _cancel_locked_task(session, task=task)
            return
        if not _holds_running_lease(task, prepared.lease_token):
            return
        if job.status == "archived":
            await _fail_locked_task(session, task=task, error_code=TENANT_JOB_ARCHIVED)
            return
        existing = (
            await session.execute(
                select(JobRequirementDraft.id).where(
                    JobRequirementDraft.tenant_id == prepared.tenant_id,
                    JobRequirementDraft.job_id == prepared.job_id,
                    JobRequirementDraft.status == "editable",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await _fail_locked_task(session, task=task, error_code=service.DRAFT_EXISTS)
            return
        session.add(
            JobRequirementDraft(
                id=uuid.uuid4(),
                tenant_id=prepared.tenant_id,
                job_id=prepared.job_id,
                task_id=prepared.task_id,
                input_snapshot_id=prepared.snapshot_id,
                requirement_schema_version_id=prepared.schema_id,
                status="editable",
                revision=1,
                result_json=result,
                created_by=prepared.actor_user_id,
            )
        )
        task.status = "succeeded"
        task.error_code = None
        task.completed_at = datetime.now(UTC)
        _clear_lease(task)
        _ = await service.append_task_event(session, task=task, payload={})
        if prepared.actor_user_id is not None:
            tenant_audit_service.record_event(
                session,
                tenant_id=prepared.tenant_id,
                actor_user_id=prepared.actor_user_id,
                action=service.ACTION_RESULT,
                target_type=service.TARGET_TYPE,
                target_id=str(prepared.task_id),
                result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
            )


async def fail_without_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedTask,
    error_code: str,
) -> None:
    async with session_factory() as session, session.begin():
        await tenant_context.set_tenant_context(session, claim.tenant_id)
        task = await _locked_task(
            session,
            tenant_id=claim.tenant_id,
            task_id=claim.task_id,
        )
        if task is None:
            return
        if task.status == "cancel_requested" and task.lease_token == claim.lease_token:
            await _cancel_locked_task(session, task=task)
            return
        if not _holds_running_lease(task, claim.lease_token):
            return
        await _fail_locked_task(session, task=task, error_code=error_code)


async def schedule_due_tasks(session: AsyncSession, *, limit: int = 100) -> int:
    changed = (
        await session.execute(
            text("SELECT schedule_due_requirement_tasks(:batch_size)"),
            {"batch_size": limit},
        )
    ).scalar_one()
    await session.commit()
    return int(changed)


async def recover_expired_task_leases(session: AsyncSession, *, limit: int = 100) -> int:
    changed = (
        await session.execute(
            text("SELECT recover_expired_requirement_tasks(:batch_size)"),
            {"batch_size": limit},
        )
    ).scalar_one()
    await session.commit()
    return int(changed)


async def run_scheduled_operation(
    operation: Callable[[AsyncSession], Awaitable[int]],
) -> int:
    settings = load_database_settings()
    engine = create_engine_from_settings(
        settings,
        database_role=REQUIREMENT_SCHEDULER_DATABASE_ROLE,
    )
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await operation(session)
    finally:
        await engine.dispose()


async def _locked_task(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> JobRequirementParsingTask | None:
    return (
        await session.execute(
            select(JobRequirementParsingTask)
            .where(
                JobRequirementParsingTask.id == task_id,
                JobRequirementParsingTask.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()


def _holds_running_lease(task: JobRequirementParsingTask | None, token: uuid.UUID) -> bool:
    return (
        task is not None
        and task.status == "running"
        and task.lease_token == token
        and task.lease_expires_at is not None
        and task.lease_expires_at > datetime.now(UTC)
    )


def _holds_active_lease(task: JobRequirementParsingTask | None, token: uuid.UUID) -> bool:
    return (
        task is not None
        and task.status in {"running", "cancel_requested"}
        and task.lease_token == token
        and task.lease_expires_at is not None
        and task.lease_expires_at > datetime.now(UTC)
    )


def _clear_lease(task: JobRequirementParsingTask) -> None:
    task.lease_token = None
    task.lease_expires_at = None
    task.last_heartbeat_at = None


async def _cancel_locked_task(
    session: AsyncSession,
    *,
    task: JobRequirementParsingTask,
) -> None:
    task.status = "cancelled"
    task.error_code = None
    task.completed_at = datetime.now(UTC)
    task.next_attempt_at = None
    _clear_lease(task)
    _ = await service.append_task_event(session, task=task, payload={})


async def _fail_locked_task(
    session: AsyncSession,
    *,
    task: JobRequirementParsingTask,
    error_code: str,
) -> None:
    task.status = "failed"
    task.error_code = error_code
    task.completed_at = datetime.now(UTC)
    task.next_attempt_at = None
    _clear_lease(task)
    _ = await service.append_task_event(
        session,
        task=task,
        payload={"error_code": error_code, "retryable": False},
    )
    _record_failure_audit(session, task=task, error_code=error_code)


def _record_failure_audit(
    session: AsyncSession,
    *,
    task: JobRequirementParsingTask,
    error_code: str,
) -> None:
    if task.created_by is None:
        return
    tenant_audit_service.record_event(
        session,
        tenant_id=task.tenant_id,
        actor_user_id=task.created_by,
        action=service.ACTION_RESULT,
        target_type=service.TARGET_TYPE,
        target_id=str(task.id),
        result=tenant_audit_service.AUDIT_RESULT_FAILURE,
        detail=error_code,
    )


def _assets_match(*, prompt: PromptVersion, schema: JobRequirementSchemaVersion) -> bool:
    return (
        prompt.id == manifest.JOB_REQUIREMENT_PROMPT_V2.id
        and schema.id == manifest.JOB_REQUIREMENT_SCHEMA_V2.id
        and prompt.compatible_schema_version_id == schema.id
        and prompt.sha256 == manifest.JOB_REQUIREMENT_PROMPT_V2.sha256
        and schema.sha256 == manifest.JOB_REQUIREMENT_SCHEMA_V2.sha256
    )


def _tenant_error(*, category: str, retryable: bool) -> str:
    if category in {"invalid_structured_output", "invalid_evidence"}:
        return TENANT_INVALID_OUTPUT
    if retryable:
        return TENANT_TEMPORARY_FAILURE
    return TENANT_CONFIGURATION_FAILURE


async def _previous_unknown_call_id(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    request_number: int,
) -> uuid.UUID | None:
    if request_number <= 1:
        return None
    return (
        await session.execute(
            select(LlmCallRecord.id)
            .join(LlmCallOutcomeEvent, LlmCallOutcomeEvent.call_id == LlmCallRecord.id)
            .where(
                LlmCallRecord.job_requirement_parsing_task_id == task_id,
                LlmCallRecord.request_number == request_number - 1,
                LlmCallOutcomeEvent.sequence_number == 1,
                LlmCallOutcomeEvent.outcome == "outcome_unknown",
            )
        )
    ).scalar_one_or_none()
