from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from relationship_network_api import audit_service
from relationship_network_api.llm_assets import manifest
from relationship_network_api.llm_assets.manifest import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
)
from relationship_network_api.models import (
    LLM_CONFIGURATION_NONTERMINAL_STATUSES,
    JobRequirementSchemaVersion,
    LlmConfigurationAttempt,
    LlmConfigurationAttemptEvent,
    LlmConfigurationAttemptStatus,
    LlmConfigurationCallBinding,
    LlmConfigurationCurrent,
    LlmConfigurationVersion,
    PlatformOutboxEvent,
    PromptVersion,
    SearchInterpretationSchemaVersion,
)
from relationship_network_api.openrouter import (
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    CallTypeBinding,
    CandidateConfiguration,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

STALE_CURRENT_CONFIGURATION: Final = "stale_current_configuration"
CONFIG_CHANGE_IN_PROGRESS: Final = "config_change_in_progress"
INCOMPATIBLE_LLM_ASSETS: Final = "incompatible_llm_assets"
ATTEMPT_NOT_FOUND: Final = "llm_configuration_attempt_not_found"
VERSION_NOT_FOUND: Final = "llm_configuration_version_not_found"

ATTEMPT_CREATE_ACTION: Final = "llm_configuration_attempt.create"
ATTEMPT_CANCEL_ACTION: Final = "llm_configuration_attempt.cancel"
ATTEMPT_COPY_ACTION: Final = "llm_configuration_attempt.copy"
OUTBOX_TOPIC: Final = "llm_configuration_attempt.execute"


class StaleCurrentConfigurationError(RuntimeError):
    pass


class IncompatibleLlmAssetsError(RuntimeError):
    pass


class LlmConfigurationAttemptNotFoundError(RuntimeError):
    pass


class LlmConfigurationVersionNotFoundError(RuntimeError):
    pass


@final
class ConfigChangeInProgressError(RuntimeError):
    def __init__(self, attempt_id: uuid.UUID) -> None:
        super().__init__(CONFIG_CHANGE_IN_PROGRESS)
        self.attempt_id: uuid.UUID = attempt_id


@final
@dataclass(frozen=True)
class SchemaSummaryView:
    id: str
    schema_id: str
    sha256: str
    field_catalog: dict[str, object]
    chinese_identity_values: list[str]
    output_limits: dict[str, int]


@final
@dataclass(frozen=True)
class PromptVersionView:
    id: str
    compatible_schema_version_id: str
    call_type: str
    sha256: str


@final
@dataclass(frozen=True)
class CallBindingView:
    prompt_version_id: str
    request_timeout_seconds: int


@final
@dataclass(frozen=True)
class ValidatedCallBinding:
    call_type: str
    prompt: PromptVersion
    catalog_schema: JobRequirementSchemaVersion
    output_schema: dict[str, object]
    output_schema_id: str
    output_schema_sha256: str
    system_prompt: str


@final
@dataclass(frozen=True)
class LlmConfigurationVersionView:
    id: uuid.UUID
    version_number: int
    provider: str
    model: str
    prompt_version_id: str
    requirement_schema_version_id: str
    temperature: float
    max_output_tokens: int
    request_timeout_seconds: int
    input_character_limit: int
    privacy_routing: dict[str, object]
    call_bindings: dict[str, CallBindingView | None]
    source_version_id: uuid.UUID | None
    source: str
    created_by: uuid.UUID | None
    created_at: datetime


@final
@dataclass(frozen=True)
class LlmConfigurationAttemptView:
    id: uuid.UUID
    status: LlmConfigurationAttemptStatus
    candidate: dict[str, object]
    expected_current_version_id: uuid.UUID
    source_version_id: uuid.UUID | None
    external_call_count: int
    structured_invalid_count: int
    probe_progress: dict[str, object]
    next_attempt_at: datetime | None
    error_code: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


@final
@dataclass(frozen=True)
class LlmConfigurationWorkspaceView:
    current: LlmConfigurationVersionView
    history: list[LlmConfigurationVersionView]
    prompt_versions: list[PromptVersionView]
    schema_versions: list[SchemaSummaryView]
    active_attempt: LlmConfigurationAttemptView | None


@final
@dataclass(frozen=True)
class LlmConfigurationAttemptEventView:
    attempt_id: uuid.UUID
    sequence_number: int
    event_type: LlmConfigurationAttemptStatus
    payload: dict[str, object]
    created_at: datetime


def _binding_view(binding: LlmConfigurationCallBinding | None) -> CallBindingView | None:
    if binding is None:
        return None
    return CallBindingView(
        prompt_version_id=binding.prompt_version_id,
        request_timeout_seconds=binding.request_timeout_seconds,
    )


def _version_view(
    version: LlmConfigurationVersion,
    bindings: dict[str, LlmConfigurationCallBinding],
) -> LlmConfigurationVersionView:
    parsing = bindings.get(CALL_TYPE_JOB_REQUIREMENT_PARSING)
    return LlmConfigurationVersionView(
        id=version.id,
        version_number=version.version_number,
        provider=version.provider,
        model=version.model,
        prompt_version_id=version.prompt_version_id,
        requirement_schema_version_id=version.requirement_schema_version_id,
        temperature=float(version.temperature),
        max_output_tokens=version.max_output_tokens,
        request_timeout_seconds=version.request_timeout_seconds,
        input_character_limit=version.input_character_limit,
        privacy_routing=version.privacy_routing,
        call_bindings={
            CALL_TYPE_JOB_REQUIREMENT_PARSING: _binding_view(parsing)
            or CallBindingView(
                prompt_version_id=version.prompt_version_id,
                request_timeout_seconds=version.request_timeout_seconds,
            ),
            CALL_TYPE_SEARCH_INTERPRETATION: _binding_view(
                bindings.get(CALL_TYPE_SEARCH_INTERPRETATION)
            ),
        },
        source_version_id=version.source_version_id,
        source=version.source,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _attempt_view(attempt: LlmConfigurationAttempt) -> LlmConfigurationAttemptView:
    candidate = dict(attempt.candidate_snapshot)
    _ = candidate.setdefault("input_character_limit", 100_000)
    return LlmConfigurationAttemptView(
        id=attempt.id,
        status=attempt.status,
        candidate=candidate,
        expected_current_version_id=attempt.expected_current_version_id,
        source_version_id=attempt.source_version_id,
        external_call_count=attempt.external_call_count,
        structured_invalid_count=attempt.structured_invalid_count,
        probe_progress=dict(attempt.probe_progress),
        next_attempt_at=attempt.next_attempt_at,
        error_code=attempt.error_code,
        created_by=attempt.created_by,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


async def load_workspace(session: AsyncSession) -> LlmConfigurationWorkspaceView:
    pointer = (
        await session.execute(
            select(LlmConfigurationCurrent).where(LlmConfigurationCurrent.singleton)
        )
    ).scalar_one()
    versions = list(
        (
            await session.execute(
                select(LlmConfigurationVersion).order_by(
                    LlmConfigurationVersion.version_number.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    current = next(version for version in versions if version.id == pointer.version_id)
    prompts = list(
        (await session.execute(select(PromptVersion).order_by(PromptVersion.created_at.desc())))
        .scalars()
        .all()
    )
    schemas = list(
        (
            await session.execute(
                select(JobRequirementSchemaVersion).order_by(
                    JobRequirementSchemaVersion.created_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    binding_rows = list(
        (await session.execute(select(LlmConfigurationCallBinding))).scalars().all()
    )
    bindings_by_version: dict[uuid.UUID, dict[str, LlmConfigurationCallBinding]] = {}
    for binding in binding_rows:
        bindings_by_version.setdefault(binding.configuration_version_id, {})[binding.call_type] = (
            binding
        )
    active = await _find_active_attempt(session)
    return LlmConfigurationWorkspaceView(
        current=_version_view(current, bindings_by_version.get(current.id, {})),
        history=[
            _version_view(version, bindings_by_version.get(version.id, {})) for version in versions
        ],
        prompt_versions=[
            PromptVersionView(
                id=prompt.id,
                compatible_schema_version_id=prompt.compatible_schema_version_id,
                call_type=prompt.call_type,
                sha256=prompt.sha256,
            )
            for prompt in prompts
        ],
        schema_versions=[
            SchemaSummaryView(
                id=schema.id,
                schema_id=schema.schema_id,
                sha256=schema.sha256,
                field_catalog=schema.field_catalog,
                chinese_identity_values=schema.chinese_identity_values,
                output_limits=schema.output_limits,
            )
            for schema in schemas
        ],
        active_attempt=None if active is None else _attempt_view(active),
    )


async def create_attempt(  # noqa: PLR0913
    session: AsyncSession,
    *,
    candidate: CandidateConfiguration,
    expected_current_version_id: uuid.UUID,
    actor_id: uuid.UUID,
    source_version_id: uuid.UUID | None = None,
    audit_action: str = ATTEMPT_CREATE_ACTION,
) -> LlmConfigurationAttemptView:
    if not candidate.has_declared_call_types():
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
    _ = await validate_candidate_assets(session, candidate)
    pointer = (
        await session.execute(
            select(LlmConfigurationCurrent).where(LlmConfigurationCurrent.singleton)
        )
    ).scalar_one()
    if pointer.version_id != expected_current_version_id:
        raise StaleCurrentConfigurationError(STALE_CURRENT_CONFIGURATION)
    active = await _find_active_attempt(session)
    if active is not None:
        raise ConfigChangeInProgressError(active.id)

    attempt = LlmConfigurationAttempt(
        id=uuid.uuid4(),
        status="queued",
        candidate_snapshot=candidate.sanitized_snapshot(),
        expected_current_version_id=expected_current_version_id,
        source_version_id=source_version_id,
        created_by=actor_id,
        external_call_count=0,
        structured_invalid_count=0,
    )
    session.add(attempt)
    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        active = await _find_active_attempt(session)
        if active is not None:
            raise ConfigChangeInProgressError(active.id) from error
        raise
    _ = await append_attempt_event(session, attempt=attempt, payload={})
    await enqueue_attempt_outbox(session, attempt_id=attempt.id)
    audit_service.record_event(
        session,
        actor_id=actor_id,
        action=audit_action,
        target_type="llm_configuration_attempt",
        target_id=str(attempt.id),
        result=audit_service.AUDIT_RESULT_SUCCESS,
    )
    await session.commit()
    return _attempt_view(attempt)


async def copy_version_as_attempt(
    session: AsyncSession,
    *,
    version_id: uuid.UUID,
    expected_current_version_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> LlmConfigurationAttemptView:
    version = (
        await session.execute(
            select(LlmConfigurationVersion).where(LlmConfigurationVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise LlmConfigurationVersionNotFoundError(VERSION_NOT_FOUND)
    binding_rows = list(
        (
            await session.execute(
                select(LlmConfigurationCallBinding).where(
                    LlmConfigurationCallBinding.configuration_version_id == version.id
                )
            )
        )
        .scalars()
        .all()
    )
    by_type = {binding.call_type: binding for binding in binding_rows}
    parsing = by_type.get(CALL_TYPE_JOB_REQUIREMENT_PARSING)
    search = by_type.get(CALL_TYPE_SEARCH_INTERPRETATION)
    candidate = CandidateConfiguration(
        model=version.model,
        temperature=float(version.temperature),
        max_output_tokens=version.max_output_tokens,
        input_character_limit=version.input_character_limit,
        bindings=(
            CallTypeBinding(
                call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                prompt_version_id=(
                    version.prompt_version_id if parsing is None else parsing.prompt_version_id
                ),
                request_timeout_seconds=(
                    version.request_timeout_seconds
                    if parsing is None
                    else parsing.request_timeout_seconds
                ),
            ),
            CallTypeBinding(
                call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                prompt_version_id=(
                    manifest.SEARCH_INTERPRETATION_PROMPT_V1.id
                    if search is None
                    else search.prompt_version_id
                ),
                request_timeout_seconds=(
                    DEFAULT_SEARCH_TIMEOUT_SECONDS
                    if search is None
                    else search.request_timeout_seconds
                ),
            ),
        ),
    )
    return await create_attempt(
        session,
        candidate=candidate,
        expected_current_version_id=expected_current_version_id,
        actor_id=actor_id,
        source_version_id=version.id,
        audit_action=ATTEMPT_COPY_ACTION,
    )


async def get_attempt(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
) -> LlmConfigurationAttemptView:
    attempt = (
        await session.execute(
            select(LlmConfigurationAttempt).where(LlmConfigurationAttempt.id == attempt_id)
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise LlmConfigurationAttemptNotFoundError(ATTEMPT_NOT_FOUND)
    return _attempt_view(attempt)


async def cancel_attempt(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> LlmConfigurationAttemptView:
    attempt = (
        await session.execute(
            select(LlmConfigurationAttempt)
            .where(LlmConfigurationAttempt.id == attempt_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise LlmConfigurationAttemptNotFoundError(ATTEMPT_NOT_FOUND)
    if attempt.status in {"queued", "retry_scheduled"}:
        attempt.status = "cancelled"
        attempt.next_attempt_at = None
        _ = await append_attempt_event(session, attempt=attempt, payload={})
    elif attempt.status == "running":
        attempt.status = "cancel_requested"
        _ = await append_attempt_event(session, attempt=attempt, payload={})
    audit_service.record_event(
        session,
        actor_id=actor_id,
        action=ATTEMPT_CANCEL_ACTION,
        target_type="llm_configuration_attempt",
        target_id=str(attempt.id),
        result=audit_service.AUDIT_RESULT_SUCCESS,
        detail=attempt.status,
    )
    await session.refresh(attempt)
    view = _attempt_view(attempt)
    await session.commit()
    return view


async def list_attempt_events(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    after_sequence: int = 0,
) -> list[LlmConfigurationAttemptEventView]:
    attempt_exists = (
        await session.execute(
            select(LlmConfigurationAttempt.id).where(LlmConfigurationAttempt.id == attempt_id)
        )
    ).scalar_one_or_none()
    if attempt_exists is None:
        raise LlmConfigurationAttemptNotFoundError(ATTEMPT_NOT_FOUND)
    events = list(
        (
            await session.execute(
                select(LlmConfigurationAttemptEvent)
                .where(
                    LlmConfigurationAttemptEvent.attempt_id == attempt_id,
                    LlmConfigurationAttemptEvent.sequence_number > after_sequence,
                )
                .order_by(LlmConfigurationAttemptEvent.sequence_number)
            )
        )
        .scalars()
        .all()
    )
    return [
        LlmConfigurationAttemptEventView(
            attempt_id=event.attempt_id,
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event in events
    ]


async def append_attempt_event(
    session: AsyncSession,
    *,
    attempt: LlmConfigurationAttempt,
    payload: dict[str, object],
) -> LlmConfigurationAttemptEvent:
    latest = (
        await session.execute(
            select(func.coalesce(func.max(LlmConfigurationAttemptEvent.sequence_number), 0)).where(
                LlmConfigurationAttemptEvent.attempt_id == attempt.id
            )
        )
    ).scalar_one()
    event = LlmConfigurationAttemptEvent(
        attempt_id=attempt.id,
        sequence_number=int(latest) + 1,
        event_type=attempt.status,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def enqueue_attempt_outbox(session: AsyncSession, *, attempt_id: uuid.UUID) -> None:
    """Insert without implicit RETURNING so writers need no Outbox read privilege."""
    _ = await session.execute(
        insert(PlatformOutboxEvent)
        .inline()
        .values(id=uuid.uuid4(), topic=OUTBOX_TOPIC, aggregate_id=attempt_id)
    )


async def validate_candidate_assets(
    session: AsyncSession,
    candidate: CandidateConfiguration,
) -> dict[str, ValidatedCallBinding]:
    try:
        manifest.validate_deployed_assets()
    except manifest.LlmAssetError as error:
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS) from error
    validated: dict[str, ValidatedCallBinding] = {}
    for binding in candidate.bindings:
        validated[binding.call_type] = await _validate_call_binding(session, binding)
    return validated


async def _validate_call_binding(
    session: AsyncSession,
    binding: CallTypeBinding,
) -> ValidatedCallBinding:
    try:
        deployed_prompt = manifest.prompt_asset(binding.prompt_version_id)
        deployed_catalog = manifest.schema_asset(deployed_prompt.compatible_schema_version_id)
    except manifest.LlmAssetError as error:
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS) from error
    if deployed_prompt.call_type != binding.call_type:
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
    prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.id == binding.prompt_version_id)
        )
    ).scalar_one_or_none()
    if (
        prompt is None
        or prompt.sha256 != deployed_prompt.sha256
        or prompt.compatible_schema_version_id != deployed_prompt.compatible_schema_version_id
        or prompt.call_type != binding.call_type
    ):
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
    catalog = (
        await session.execute(
            select(JobRequirementSchemaVersion).where(
                JobRequirementSchemaVersion.id == prompt.compatible_schema_version_id
            )
        )
    ).scalar_one_or_none()
    if (
        catalog is None
        or catalog.sha256 != deployed_catalog.sha256
        or catalog.schema_id != deployed_catalog.schema_id
    ):
        raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
    if binding.call_type == CALL_TYPE_SEARCH_INTERPRETATION:
        output_id = deployed_prompt.output_schema_version_id
        if output_id is None:
            raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
        try:
            deployed_output = manifest.search_interpretation_schema_asset(output_id)
        except manifest.LlmAssetError as error:
            raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS) from error
        output_row = (
            await session.execute(
                select(SearchInterpretationSchemaVersion).where(
                    SearchInterpretationSchemaVersion.id == output_id
                )
            )
        ).scalar_one_or_none()
        if (
            output_row is None
            or output_row.sha256 != deployed_output.sha256
            or output_row.schema_id != deployed_output.schema_id
            or prompt.output_schema_version_id != output_id
        ):
            raise IncompatibleLlmAssetsError(INCOMPATIBLE_LLM_ASSETS)
        output_schema = manifest.read_search_interpretation_schema(output_id)
        output_schema_id = output_row.id
        output_schema_sha256 = output_row.sha256
    else:
        output_schema = manifest.read_requirement_schema(catalog.id)
        output_schema_id = catalog.id
        output_schema_sha256 = catalog.sha256
    return ValidatedCallBinding(
        call_type=binding.call_type,
        prompt=prompt,
        catalog_schema=catalog,
        output_schema=output_schema,
        output_schema_id=output_schema_id,
        output_schema_sha256=output_schema_sha256,
        system_prompt=prompt.content,
    )


async def _find_active_attempt(session: AsyncSession) -> LlmConfigurationAttempt | None:
    return (
        await session.execute(
            select(LlmConfigurationAttempt).where(
                LlmConfigurationAttempt.status.in_(LLM_CONFIGURATION_NONTERMINAL_STATUSES)
            )
        )
    ).scalar_one_or_none()
