from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast, final

import anyio
from sqlalchemy import func, select, text

from relationship_network_api import (
    audit_service,
    durable_task,
)
from relationship_network_api import (
    llm_call_audit_service as call_audit,
)
from relationship_network_api import (
    llm_configuration_service as service,
)
from relationship_network_api.config import PlatformLlmSettings, load_platform_llm_settings
from relationship_network_api.db import (
    PLATFORM_WORKER_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.durable_task import (
    HEARTBEAT_SECONDS,
    MAX_EXTERNAL_CALLS,
    MAX_STRUCTURED_INVALID_CALLS,
    lease_seconds_for_timeout,
)
from relationship_network_api.models import (
    LlmCallOutcomeEvent,
    LlmCallRecord,
    LlmConfigurationAttempt,
    LlmConfigurationVersion,
)
from relationship_network_api.openrouter import (
    CandidateConfiguration,
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
    OpenRouterProbeResult,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

LEASE_SECONDS: Final = lease_seconds_for_timeout(300)
ACTIVATION_ACTION: Final = "llm_configuration.activate"


def retry_delay_seconds(request_number: int) -> int:
    """Preserve the worker API while sharing the durable-task backoff policy."""
    return durable_task.retry_delay_seconds(request_number)


ATTEMPT_RESULT_ACTION: Final = "llm_configuration_attempt.finish"
ACTIVATE_VERSION_FUNCTION: Final = "activate_llm_configuration_version"
ACTIVATE_VERSION_SQL: Final = f"SELECT {ACTIVATE_VERSION_FUNCTION}(:expected_version, :new_version)"


@final
@dataclass(frozen=True)
class ClaimedAttempt:
    id: uuid.UUID
    lease_token: uuid.UUID
    candidate: CandidateConfiguration


@final
@dataclass(frozen=True)
class PreparedCall:
    call_id: uuid.UUID
    request_number: int
    schema_version_id: str


async def process_attempt(
    attempt_id: uuid.UUID,
    *,
    settings: PlatformLlmSettings | None = None,
) -> None:
    resolved_settings = settings or load_platform_llm_settings()
    engine = create_engine_from_settings(
        resolved_settings,
        database_role=PLATFORM_WORKER_DATABASE_ROLE,
    )
    session_factory = create_session_factory(engine)
    try:
        claim = await claim_attempt(session_factory, attempt_id=attempt_id)
        if claim is None:
            return
        if resolved_settings.openrouter_api_key is None:
            await fail_without_call(
                session_factory,
                claim=claim,
                error_code="openrouter_not_configured",
            )
            return
        try:
            key_ring = call_audit.RawResponseKeyRing.parse(
                resolved_settings.llm_raw_response_keys.get_secret_value(),
                resolved_settings.llm_raw_response_active_key_id,
            )
            _ = key_ring.require_active_key()
        except call_audit.RawResponseKeyConfigurationError:
            await fail_without_call(
                session_factory,
                claim=claim,
                error_code="raw_response_encryption_not_configured",
            )
            return
        try:
            prepared = await prepare_call(session_factory, claim=claim)
        except service.IncompatibleLlmAssetsError:
            await fail_without_call(
                session_factory,
                claim=claim,
                error_code=service.INCOMPATIBLE_LLM_ASSETS,
            )
            return
        if prepared is None:
            return
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(
                api_key=resolved_settings.openrouter_api_key.get_secret_value(),
                base_url=resolved_settings.openrouter_base_url,
                site_url=resolved_settings.openrouter_site_url,
                site_name=resolved_settings.openrouter_site_name,
            )
        )
        stop_heartbeat = anyio.Event()
        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(
                heartbeat_loop,
                session_factory,
                claim,
                stop_heartbeat,
            )
            started_ns = time.monotonic_ns()
            try:
                result = await adapter.probe(claim.candidate)
            except OpenRouterAdapterError as error:
                duration_ms = max((time.monotonic_ns() - started_ns) // 1_000_000, 0)
                stop_heartbeat.set()
                await handle_probe_error(
                    session_factory,
                    claim=claim,
                    prepared=prepared,
                    error=error,
                    key_ring=key_ring,
                    duration_ms=duration_ms,
                )
            else:
                duration_ms = max((time.monotonic_ns() - started_ns) // 1_000_000, 0)
                stop_heartbeat.set()
                await handle_probe_success(
                    session_factory,
                    claim=claim,
                    prepared=prepared,
                    result=result,
                    key_ring=key_ring,
                    duration_ms=duration_ms,
                )
    finally:
        await engine.dispose()


async def claim_attempt(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    attempt_id: uuid.UUID,
) -> ClaimedAttempt | None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, attempt_id)
        if attempt is None or attempt.status != "queued":
            return None
        token = uuid.uuid4()
        now = datetime.now(UTC)
        attempt.status = "running"
        attempt.lease_token = token
        attempt.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        attempt.last_heartbeat_at = now
        attempt.next_attempt_at = None
        _ = await service.append_attempt_event(session, attempt=attempt, payload={})
        candidate = CandidateConfiguration(
            model=cast("str", attempt.candidate_snapshot["model"]),
            prompt_version_id=cast("str", attempt.candidate_snapshot["prompt_version_id"]),
            temperature=cast("float", attempt.candidate_snapshot["temperature"]),
            max_output_tokens=cast("int", attempt.candidate_snapshot["max_output_tokens"]),
            request_timeout_seconds=cast(
                "int", attempt.candidate_snapshot["request_timeout_seconds"]
            ),
            input_character_limit=cast(
                "int", attempt.candidate_snapshot.get("input_character_limit", 100_000)
            ),
        )
        return ClaimedAttempt(id=attempt.id, lease_token=token, candidate=candidate)


async def prepare_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
) -> PreparedCall | None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None or not _holds_running_lease(attempt, claim.lease_token):
            return None
        prompt, schema = await service.validate_candidate_assets(session, claim.candidate)
        request_number = attempt.external_call_count + 1
        if request_number > MAX_EXTERNAL_CALLS:
            attempt.status = "failed"
            attempt.error_code = "request_budget_exhausted"
            _clear_lease(attempt)
            _ = await service.append_attempt_event(
                session,
                attempt=attempt,
                payload={"error_code": attempt.error_code, "retryable": False},
            )
            return None
        request_hash = _probe_request_hash(claim.candidate)
        input_sha256, input_length = _probe_input_fingerprint(claim.candidate)
        previous_call_id = await _previous_unknown_call_id(
            session,
            attempt_id=attempt.id,
            request_number=request_number,
        )
        call = LlmCallRecord(
            id=uuid.uuid4(),
            scope="platform",
            tenant_id=None,
            call_type="config_probe",
            platform_attempt_id=attempt.id,
            job_requirement_parsing_task_id=None,
            configuration_version_id=None,
            input_snapshot_id=None,
            correlation_call_id=previous_call_id,
            request_number=request_number,
            model=claim.candidate.model,
            prompt_version_id=claim.candidate.prompt_version_id,
            prompt_sha256=prompt.sha256,
            requirement_schema_version_id=schema.id,
            requirement_schema_sha256=schema.sha256,
            input_sources_summary={"kind": "fixed_platform_probe", "contains_business_data": False},
            input_sha256=input_sha256,
            input_length=input_length,
            parameters={
                "max_output_tokens": claim.candidate.max_output_tokens,
                "request_timeout_seconds": claim.candidate.request_timeout_seconds,
                "temperature": claim.candidate.temperature,
            },
            request_hash=request_hash,
        )
        attempt.external_call_count = request_number
        session.add(call)
        await session.flush()
        return PreparedCall(
            call_id=call.id,
            request_number=request_number,
            schema_version_id=schema.id,
        )


async def heartbeat_loop(
    session_factory: async_sessionmaker[AsyncSession],
    claim: ClaimedAttempt,
    stop: anyio.Event,
) -> None:
    while True:
        with anyio.move_on_after(HEARTBEAT_SECONDS):
            await stop.wait()
        if stop.is_set():
            return
        async with session_factory() as session, session.begin():
            attempt = await _locked_attempt(session, claim.id)
            if attempt is None or not _holds_running_lease(attempt, claim.lease_token):
                return
            now = datetime.now(UTC)
            attempt.last_heartbeat_at = now
            attempt.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)


async def handle_probe_success(  # noqa: PLR0913
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
    prepared: PreparedCall,
    result: OpenRouterProbeResult,
    key_ring: call_audit.RawResponseKeyRing,
    duration_ms: int,
) -> None:
    persisted = await call_audit.persist_call_response(
        session_factory,
        call_id=prepared.call_id,
        key_ring=key_ring,
        requested_outcome="succeeded",
        category="",
        exchange=result.exchange,
        result=result,
        duration_ms=duration_ms,
    )
    if persisted.is_late_response:
        return
    async with session_factory() as session:
        async with session.begin():
            attempt = await _locked_attempt(session, claim.id)
            if attempt is None:
                return
            if attempt.status == "cancel_requested":
                attempt.status = "cancelled"
                _clear_lease(attempt)
                _ = await service.append_attempt_event(session, attempt=attempt, payload={})
                return
            if not _holds_running_lease(attempt, claim.lease_token):
                return
            next_number = (
                int(
                    (
                        await session.execute(
                            select(
                                func.coalesce(func.max(LlmConfigurationVersion.version_number), 0)
                            )
                        )
                    ).scalar_one()
                )
                + 1
            )
            version = LlmConfigurationVersion(
                id=uuid.uuid4(),
                version_number=next_number,
                provider="openrouter",
                model=claim.candidate.model,
                prompt_version_id=claim.candidate.prompt_version_id,
                requirement_schema_version_id=prepared.schema_version_id,
                temperature=claim.candidate.temperature,
                max_output_tokens=claim.candidate.max_output_tokens,
                request_timeout_seconds=claim.candidate.request_timeout_seconds,
                input_character_limit=claim.candidate.input_character_limit,
                privacy_routing={
                    "data_collection": "deny",
                    "require_parameters": True,
                    "zdr": True,
                },
                source_version_id=attempt.source_version_id,
                created_by=attempt.created_by,
                source="probe",
            )
            session.add(version)
            await session.flush()
            activated = bool(
                (
                    await session.execute(
                        text(ACTIVATE_VERSION_SQL),
                        {
                            "expected_version": attempt.expected_current_version_id,
                            "new_version": version.id,
                        },
                    )
                ).scalar_one()
            )
            if not activated:
                await session.rollback()
            else:
                attempt.status = "succeeded"
                attempt.error_code = None
                _clear_lease(attempt)
                _ = await service.append_attempt_event(
                    session,
                    attempt=attempt,
                    payload={"configuration_version_id": str(version.id)},
                )
                audit_service.record_event(
                    session,
                    actor_id=attempt.created_by,
                    action=ACTIVATION_ACTION,
                    target_type="llm_configuration_version",
                    target_id=str(version.id),
                    result=audit_service.AUDIT_RESULT_SUCCESS,
                )
                return
        await mark_conflicted(session_factory, claim=claim)


async def handle_probe_error(  # noqa: PLR0913
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
    prepared: PreparedCall,
    error: OpenRouterAdapterError,
    key_ring: call_audit.RawResponseKeyRing,
    duration_ms: int,
) -> None:
    persisted = await call_audit.persist_call_response(
        session_factory,
        call_id=prepared.call_id,
        key_ring=key_ring,
        requested_outcome="outcome_unknown" if error.outcome_unknown else "failed",
        category=error.category,
        exchange=error.exchange,
        result=None,
        duration_ms=duration_ms,
    )
    if persisted.is_late_response:
        return
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None:
            return
        if attempt.status == "cancel_requested":
            attempt.status = "cancelled"
            _clear_lease(attempt)
            _ = await service.append_attempt_event(session, attempt=attempt, payload={})
            return
        if not _holds_running_lease(attempt, claim.lease_token):
            return
        is_structured_invalid = error.category == "invalid_structured_output"
        if is_structured_invalid:
            attempt.structured_invalid_count += 1
        can_retry = (
            error.retryable
            and attempt.external_call_count < MAX_EXTERNAL_CALLS
            and (
                not is_structured_invalid
                or attempt.structured_invalid_count < MAX_STRUCTURED_INVALID_CALLS
            )
        )
        attempt.error_code = error.category
        if can_retry:
            delay_seconds = error.retry_after_seconds
            if delay_seconds is None:
                delay_seconds = retry_delay_seconds(attempt.external_call_count)
            attempt.status = "retry_scheduled"
            next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            attempt.next_attempt_at = next_attempt_at
            payload: dict[str, object] = {
                "error_code": error.category,
                "next_attempt_at": next_attempt_at.isoformat(),
                "retryable": True,
            }
        else:
            attempt.status = "failed"
            attempt.next_attempt_at = None
            payload = {"error_code": error.category, "retryable": False}
        _clear_lease(attempt)
        _ = await service.append_attempt_event(session, attempt=attempt, payload=payload)
        audit_service.record_event(
            session,
            actor_id=attempt.created_by,
            action=ATTEMPT_RESULT_ACTION,
            target_type="llm_configuration_attempt",
            target_id=str(attempt.id),
            result=audit_service.AUDIT_RESULT_FAILURE,
            detail=error.category,
        )


async def fail_without_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
    error_code: str,
) -> None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None or not _holds_running_lease(attempt, claim.lease_token):
            return
        attempt.status = "failed"
        attempt.error_code = error_code
        _clear_lease(attempt)
        _ = await service.append_attempt_event(
            session,
            attempt=attempt,
            payload={"error_code": error_code, "retryable": False},
        )


async def mark_conflicted(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
) -> None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None or not _holds_running_lease(attempt, claim.lease_token):
            return
        attempt.status = "conflicted"
        attempt.error_code = service.STALE_CURRENT_CONFIGURATION
        _clear_lease(attempt)
        _ = await service.append_attempt_event(
            session,
            attempt=attempt,
            payload={"error_code": service.STALE_CURRENT_CONFIGURATION, "retryable": False},
        )


async def schedule_due_attempts(session: AsyncSession, *, limit: int = 100) -> int:
    attempts = list(
        (
            await session.execute(
                select(LlmConfigurationAttempt)
                .where(
                    LlmConfigurationAttempt.status == "retry_scheduled",
                    LlmConfigurationAttempt.next_attempt_at <= func.now(),
                )
                .order_by(LlmConfigurationAttempt.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for attempt in attempts:
        attempt.status = "queued"
        attempt.next_attempt_at = None
        _ = await service.append_attempt_event(session, attempt=attempt, payload={})
        await service.enqueue_attempt_outbox(session, attempt_id=attempt.id)
    await session.commit()
    return len(attempts)


async def recover_expired_attempt_leases(session: AsyncSession, *, limit: int = 100) -> int:
    attempts = list(
        (
            await session.execute(
                select(LlmConfigurationAttempt)
                .where(
                    LlmConfigurationAttempt.status.in_(("running", "cancel_requested")),
                    LlmConfigurationAttempt.lease_expires_at <= func.now(),
                )
                .order_by(LlmConfigurationAttempt.lease_expires_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for attempt in attempts:
        if attempt.status == "cancel_requested":
            attempt.status = "cancelled"
            _clear_lease(attempt)
            _ = await service.append_attempt_event(session, attempt=attempt, payload={})
            continue
        await _record_missing_outcome_unknown(session, attempt.id)
        attempt.status = "queued"
        _clear_lease(attempt)
        _ = await service.append_attempt_event(
            session,
            attempt=attempt,
            payload={"error_code": "lease_expired", "retryable": True},
        )
        await service.enqueue_attempt_outbox(session, attempt_id=attempt.id)
    await session.commit()
    return len(attempts)


async def run_scheduled_operation(
    operation: Callable[[AsyncSession], Awaitable[int]],
) -> int:
    settings = load_platform_llm_settings()
    engine = create_engine_from_settings(settings, database_role=PLATFORM_WORKER_DATABASE_ROLE)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await operation(session)
    finally:
        await engine.dispose()


async def _locked_attempt(
    session: AsyncSession,
    attempt_id: uuid.UUID,
) -> LlmConfigurationAttempt | None:
    return (
        await session.execute(
            select(LlmConfigurationAttempt)
            .where(LlmConfigurationAttempt.id == attempt_id)
            .with_for_update()
        )
    ).scalar_one_or_none()


def _holds_running_lease(
    attempt: LlmConfigurationAttempt | None,
    token: uuid.UUID,
) -> bool:
    return attempt is not None and attempt.status == "running" and attempt.lease_token == token


def _clear_lease(attempt: LlmConfigurationAttempt) -> None:
    attempt.lease_token = None
    attempt.lease_expires_at = None
    attempt.last_heartbeat_at = None


def _probe_request_hash(candidate: CandidateConfiguration) -> str:
    payload = OpenRouterAdapter(
        OpenRouterClientConfig(api_key="not-persisted")
    ).build_probe_payload(candidate)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _probe_input_fingerprint(candidate: CandidateConfiguration) -> tuple[str, int]:
    payload = OpenRouterAdapter(
        OpenRouterClientConfig(api_key="not-persisted")
    ).build_probe_payload(candidate)
    messages = cast("list[dict[str, str]]", payload["messages"])
    serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    content_length = sum(len(message["content"]) for message in messages)
    return hashlib.sha256(serialized.encode()).hexdigest(), content_length


async def _previous_unknown_call_id(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    request_number: int,
) -> uuid.UUID | None:
    if request_number <= 1:
        return None
    return (
        await session.execute(
            select(LlmCallRecord.id)
            .join(LlmCallOutcomeEvent, LlmCallOutcomeEvent.call_id == LlmCallRecord.id)
            .where(
                LlmCallRecord.platform_attempt_id == attempt_id,
                LlmCallRecord.request_number == request_number - 1,
                LlmCallOutcomeEvent.sequence_number == 1,
                LlmCallOutcomeEvent.outcome == "outcome_unknown",
            )
        )
    ).scalar_one_or_none()


async def _record_missing_outcome_unknown(session: AsyncSession, attempt_id: uuid.UUID) -> None:
    call = (
        await session.execute(
            select(LlmCallRecord)
            .where(LlmCallRecord.platform_attempt_id == attempt_id)
            .order_by(LlmCallRecord.request_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if call is None:
        return
    outcome_exists = (
        await session.execute(
            select(LlmCallOutcomeEvent.call_id).where(LlmCallOutcomeEvent.call_id == call.id)
        )
    ).scalar_one_or_none()
    if outcome_exists is None:
        session.add(
            LlmCallOutcomeEvent(
                call_id=call.id,
                sequence_number=1,
                scope=call.scope,
                tenant_id=call.tenant_id,
                outcome="outcome_unknown",
                category="lease_expired",
            )
        )
