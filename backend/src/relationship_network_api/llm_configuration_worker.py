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
from relationship_network_api.job_requirement_validation import (
    RequirementResultValidationError,
    validate_requirement_result,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.llm_assets.manifest import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
    DECLARED_CALL_TYPES,
)
from relationship_network_api.models import (
    LlmCallOutcomeEvent,
    LlmCallRecord,
    LlmConfigurationAttempt,
    LlmConfigurationCallBinding,
    LlmConfigurationVersion,
)
from relationship_network_api.openrouter import (
    PARSING_PROBE_SOURCES,
    CandidateConfiguration,
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
)
from relationship_network_api.search_interpretation_validation import (
    SearchInterpretationValidationError,
    validate_search_interpretation,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

LEASE_SECONDS: Final = lease_seconds_for_timeout(300)
ACTIVATION_ACTION: Final = "llm_configuration.activate"
INCOMPATIBLE_CANDIDATE_SNAPSHOT: Final = "incompatible_candidate_snapshot"
SUCCEEDED_CALL_TYPES_KEY: Final = "succeeded_call_types"


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
    succeeded_call_types: tuple[str, ...]


@final
@dataclass(frozen=True)
class PreparedCall:
    call_id: uuid.UUID
    request_number: int
    call_type: str
    catalog_schema_id: str
    output_schema_id: str
    system_prompt: str
    schema: dict[str, object]


async def process_attempt(  # noqa: C901, PLR0911, PLR0915
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
            remaining = [
                call_type
                for call_type in DECLARED_CALL_TYPES
                if call_type not in claim.succeeded_call_types
            ]
            try:
                for call_type in remaining:
                    try:
                        prepared = await prepare_call(
                            session_factory,
                            claim=claim,
                            call_type=call_type,
                        )
                    except service.IncompatibleLlmAssetsError:
                        stop_heartbeat.set()
                        await fail_without_call(
                            session_factory,
                            claim=claim,
                            error_code=service.INCOMPATIBLE_LLM_ASSETS,
                        )
                        return
                    if prepared is None:
                        stop_heartbeat.set()
                        return
                    started_ns = time.monotonic_ns()
                    try:
                        result = await adapter.probe(
                            claim.candidate,
                            call_type=prepared.call_type,
                            system_prompt=prepared.system_prompt,
                            schema=prepared.schema,
                        )
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
                        return
                    duration_ms = max((time.monotonic_ns() - started_ns) // 1_000_000, 0)
                    validation_error = _probe_validation_error(prepared, result.content)
                    if validation_error is not None:
                        stop_heartbeat.set()
                        await handle_probe_error(
                            session_factory,
                            claim=claim,
                            prepared=prepared,
                            error=OpenRouterAdapterError(
                                validation_error,
                                retryable=True,
                                exchange=result.exchange,
                            ),
                            key_ring=key_ring,
                            duration_ms=duration_ms,
                        )
                        return
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
                        stop_heartbeat.set()
                        return
                    recorded = await record_type_success(
                        session_factory,
                        claim=claim,
                        prepared=prepared,
                    )
                    if recorded is None:
                        stop_heartbeat.set()
                        return
                    claim = recorded
                stop_heartbeat.set()
                await enable_probed_configuration(session_factory, claim=claim)
            finally:
                stop_heartbeat.set()
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
        try:
            candidate = CandidateConfiguration.from_snapshot(attempt.candidate_snapshot)
        except (KeyError, TypeError, ValueError):
            attempt.status = "failed"
            attempt.error_code = INCOMPATIBLE_CANDIDATE_SNAPSHOT
            attempt.lease_token = None
            attempt.lease_expires_at = None
            attempt.last_heartbeat_at = None
            _ = await service.append_attempt_event(
                session,
                attempt=attempt,
                payload={"error_code": INCOMPATIBLE_CANDIDATE_SNAPSHOT, "retryable": False},
            )
            return None
        if not candidate.has_declared_call_types():
            attempt.status = "failed"
            attempt.error_code = INCOMPATIBLE_CANDIDATE_SNAPSHOT
            attempt.lease_token = None
            attempt.lease_expires_at = None
            attempt.last_heartbeat_at = None
            _ = await service.append_attempt_event(
                session,
                attempt=attempt,
                payload={"error_code": INCOMPATIBLE_CANDIDATE_SNAPSHOT, "retryable": False},
            )
            return None
        _ = await service.append_attempt_event(session, attempt=attempt, payload={})
        return ClaimedAttempt(
            id=attempt.id,
            lease_token=token,
            candidate=candidate,
            succeeded_call_types=_succeeded_call_types(attempt.probe_progress),
        )


async def prepare_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
    call_type: str,
) -> PreparedCall | None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None or not _holds_running_lease(attempt, claim.lease_token):
            return None
        validated = await service.validate_candidate_assets(session, claim.candidate)
        binding = validated[call_type]
        timeout_seconds = claim.candidate.binding_for(call_type).request_timeout_seconds
        request_number = attempt.external_call_count + 1
        if request_number > MAX_EXTERNAL_CALLS:
            attempt.status = "failed"
            attempt.error_code = "request_budget_exhausted"
            _clear_lease(attempt)
            _ = await service.append_attempt_event(
                session,
                attempt=attempt,
                payload={
                    "error_code": attempt.error_code,
                    "probed_call_type": call_type,
                    "retryable": False,
                    SUCCEEDED_CALL_TYPES_KEY: list(_succeeded_call_types(attempt.probe_progress)),
                },
            )
            return None
        request_hash = _probe_request_hash(
            claim.candidate,
            call_type=call_type,
            system_prompt=binding.system_prompt,
            schema=binding.output_schema,
        )
        input_sha256, input_length = _probe_input_fingerprint(
            claim.candidate,
            call_type=call_type,
            system_prompt=binding.system_prompt,
            schema=binding.output_schema,
        )
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
            prompt_version_id=binding.prompt.id,
            prompt_sha256=binding.prompt.sha256,
            requirement_schema_version_id=binding.catalog_schema.id,
            requirement_schema_sha256=binding.catalog_schema.sha256,
            input_sources_summary={
                "contains_business_data": False,
                "kind": "fixed_platform_probe",
                "output_schema_id": binding.output_schema_id,
                "probed_call_type": call_type,
            },
            input_sha256=input_sha256,
            input_length=input_length,
            parameters={
                "max_output_tokens": claim.candidate.max_output_tokens,
                "request_timeout_seconds": timeout_seconds,
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
            call_type=call_type,
            catalog_schema_id=binding.catalog_schema.id,
            output_schema_id=binding.output_schema_id,
            system_prompt=binding.system_prompt,
            schema=binding.output_schema,
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


async def record_type_success(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
    prepared: PreparedCall,
) -> ClaimedAttempt | None:
    async with session_factory() as session, session.begin():
        attempt = await _locked_attempt(session, claim.id)
        if attempt is None:
            return None
        if attempt.status == "cancel_requested":
            attempt.status = "cancelled"
            _clear_lease(attempt)
            _ = await service.append_attempt_event(session, attempt=attempt, payload={})
            return None
        if not _holds_running_lease(attempt, claim.lease_token):
            return None
        succeeded = list(_succeeded_call_types(attempt.probe_progress))
        if prepared.call_type not in succeeded:
            succeeded.append(prepared.call_type)
        attempt.probe_progress = {SUCCEEDED_CALL_TYPES_KEY: succeeded}
        _ = await service.append_attempt_event(
            session,
            attempt=attempt,
            payload={
                "probed_call_type": prepared.call_type,
                SUCCEEDED_CALL_TYPES_KEY: succeeded,
            },
        )
        return ClaimedAttempt(
            id=claim.id,
            lease_token=claim.lease_token,
            candidate=claim.candidate,
            succeeded_call_types=tuple(succeeded),
        )


async def enable_probed_configuration(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claim: ClaimedAttempt,
) -> None:
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
            validated = await service.validate_candidate_assets(session, claim.candidate)
            parsing = validated[CALL_TYPE_JOB_REQUIREMENT_PARSING]
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
                prompt_version_id=parsing.prompt.id,
                requirement_schema_version_id=parsing.catalog_schema.id,
                temperature=claim.candidate.temperature,
                max_output_tokens=claim.candidate.max_output_tokens,
                request_timeout_seconds=claim.candidate.binding_for(
                    CALL_TYPE_JOB_REQUIREMENT_PARSING
                ).request_timeout_seconds,
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
            for binding in claim.candidate.bindings:
                session.add(
                    LlmConfigurationCallBinding(
                        configuration_version_id=version.id,
                        call_type=binding.call_type,
                        prompt_version_id=binding.prompt_version_id,
                        request_timeout_seconds=binding.request_timeout_seconds,
                    )
                )
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
                    payload={
                        "configuration_version_id": str(version.id),
                        SUCCEEDED_CALL_TYPES_KEY: list(claim.succeeded_call_types),
                    },
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
                "probed_call_type": prepared.call_type,
                "retryable": True,
                SUCCEEDED_CALL_TYPES_KEY: list(_succeeded_call_types(attempt.probe_progress)),
            }
        else:
            attempt.status = "failed"
            attempt.next_attempt_at = None
            payload = {
                "error_code": error.category,
                "probed_call_type": prepared.call_type,
                "retryable": False,
                SUCCEEDED_CALL_TYPES_KEY: list(_succeeded_call_types(attempt.probe_progress)),
            }
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


def _probe_request_hash(
    candidate: CandidateConfiguration,
    *,
    call_type: str,
    system_prompt: str,
    schema: dict[str, object],
) -> str:
    payload = OpenRouterAdapter(
        OpenRouterClientConfig(api_key="not-persisted")
    ).build_probe_payload(
        candidate,
        call_type=call_type,
        system_prompt=system_prompt,
        schema=schema,
    )
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _probe_input_fingerprint(
    candidate: CandidateConfiguration,
    *,
    call_type: str,
    system_prompt: str,
    schema: dict[str, object],
) -> tuple[str, int]:
    payload = OpenRouterAdapter(
        OpenRouterClientConfig(api_key="not-persisted")
    ).build_probe_payload(
        candidate,
        call_type=call_type,
        system_prompt=system_prompt,
        schema=schema,
    )
    messages = cast("list[dict[str, str]]", payload["messages"])
    serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    content_length = sum(len(message["content"]) for message in messages)
    return hashlib.sha256(serialized.encode()).hexdigest(), content_length


def _succeeded_call_types(progress: dict[str, object]) -> tuple[str, ...]:
    raw = progress.get(SUCCEEDED_CALL_TYPES_KEY, [])
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _probe_validation_error(prepared: PreparedCall, content: dict[str, object]) -> str | None:
    catalog = manifest.schema_asset(prepared.catalog_schema_id)
    try:
        if prepared.call_type == CALL_TYPE_JOB_REQUIREMENT_PARSING:
            source_texts = {
                source["source_id"]: source["content"] for source in PARSING_PROBE_SOURCES
            }
            _ = validate_requirement_result(
                content,
                schema=prepared.schema,
                asset=catalog,
                source_texts=source_texts,
            )
        else:
            if prepared.call_type != CALL_TYPE_SEARCH_INTERPRETATION:
                return "invalid_structured_output"
            _ = validate_search_interpretation(
                content,
                schema=prepared.schema,
                catalog_asset=catalog,
            )
    except (RequirementResultValidationError, SearchInterpretationValidationError):
        return "invalid_structured_output"
    return None


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
