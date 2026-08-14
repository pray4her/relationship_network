"""Natural-language search runs: interpret, recall, freeze, and reopen.

A run is created before the search interpretation call and completed (or moved
to a recoverable terminal failure) inside one request; it is not a queued
task. Local talent get-or-create runs under the restricted talent-sync role
(ADR 0026), while the run and its hit snapshots stay tenant-scoped under the
application role.
"""

from __future__ import annotations

import hashlib
import json
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast, final

from sqlalchemy import ColumnElement, func, select

from relationship_network_api import (
    llm_call_audit_service,
    talent_identity_service,
    tenant_audit_service,
    tenant_context,
    usage_service,
)
from relationship_network_api.db import (
    TALENT_SYNC_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
    SEARCH_RUN_STATUS_FAILED,
    SEARCH_RUN_STATUS_IN_PROGRESS,
    SEARCH_RUN_STATUS_SUCCEEDED,
    LlmCallRecord,
    LlmConfigurationCallBinding,
    LlmConfigurationCurrent,
    LlmConfigurationVersion,
    NaturalLanguageSearchRun,
    NaturalLanguageSearchRunFailureReason,
    NaturalLanguageSearchRunStatus,
    PromptVersion,
    SearchHitSnapshot,
    SearchInterpretationSchemaVersion,
)
from relationship_network_api.openrouter import (
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    CallTypeBinding,
    CandidateConfiguration,
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
)
from relationship_network_api.search_base import (
    SearchBaseAdapterError,
    search_base_adapter_from_settings,
)
from relationship_network_api.search_base_contract import (
    MAX_SEARCH_HIT_LIMIT,
    HardCondition,
    HardConditionValue,
    SearchHit,
)
from relationship_network_api.search_interpretation_validation import (
    SearchInterpretationValidationError,
    validate_search_interpretation,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from relationship_network_api.config import AppSettings

MAX_UTTERANCE_CHARACTERS: Final = 4000
"""NFC+LF-normalized search utterance ceiling, in Unicode characters."""

SORT_KEYS: Final[tuple[str, ...]] = (
    "display_name",
    "current_affiliation",
    "country",
    "chinese_identity",
    "h_index",
    "total_citations",
    "qs_top200_rank",
    "world_top500_rank",
)
SORT_KEY_SEMANTIC: Final = "semantic_score"

INVALID_UTTERANCE_DETAIL: Final = "invalid_utterance"
IDEMPOTENCY_CONFLICT_DETAIL: Final = "search_idempotency_fingerprint_conflict"
CREATION_RATE_LIMITED_DETAIL: Final = "search_creation_rate_limited"
SEARCH_IN_PROGRESS_DETAIL: Final = "search_in_progress"
SEARCH_QUOTA_EXCEEDED_DETAIL: Final = "search_quota_exceeded"
SEARCH_RUN_NOT_FOUND_DETAIL: Final = "search_run_not_found"
INVALID_SORT_DETAIL: Final = "invalid_sort"

AUDIT_ACTION_SUCCEEDED: Final = "search.run_succeeded"
AUDIT_ACTION_FAILED: Final = "search.run_failed"
AUDIT_ACTION_REJECTED: Final = "search.run_rejected"
AUDIT_TARGET_TYPE: Final = "natural_language_search_run"
AUDIT_REJECTED_TARGET_TYPE: Final = "natural_language_search"


class SearchRunError(RuntimeError):
    """Base class for search-run failures mapped to stable HTTP details."""

    detail: str

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@final
class InvalidUtteranceError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(INVALID_UTTERANCE_DETAIL)


@final
class SearchIdempotencyConflictError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(IDEMPOTENCY_CONFLICT_DETAIL)


@final
class SearchCreationRateLimitedError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(CREATION_RATE_LIMITED_DETAIL)


@final
class SearchInProgressError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(SEARCH_IN_PROGRESS_DETAIL)


@final
class SearchQuotaExceededError(SearchRunError):
    def __init__(self, run_id: uuid.UUID) -> None:
        super().__init__(SEARCH_QUOTA_EXCEEDED_DETAIL)
        self.run_id = run_id


@final
class SearchRunNotFoundError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(SEARCH_RUN_NOT_FOUND_DETAIL)


@final
class InvalidSortError(SearchRunError):
    def __init__(self) -> None:
        super().__init__(INVALID_SORT_DETAIL)


@dataclass(frozen=True)
class SearchHitSnapshotView:
    id: uuid.UUID
    local_talent_id: uuid.UUID
    canonical_person_id: str
    display_name: str
    current_affiliation: str
    country: str
    chinese_identity: str
    h_index: int
    total_citations: int
    qs_top200_rank: int | None
    world_top500_rank: int | None
    has_contact: bool | None
    data_version: str
    hit_publications: list[dict[str, object]]
    semantic_score: float | None
    sort_position: int


@dataclass(frozen=True)
class SearchRunView:
    id: uuid.UUID
    status: NaturalLanguageSearchRunStatus
    failure_reason: NaturalLanguageSearchRunFailureReason | None
    utterance: str
    utterance_length: int
    idempotency_key: str
    llm_configuration_version_id: uuid.UUID
    search_contract_version: str
    data_version: str | None
    request_id: str | None
    has_research_topic: bool
    search_interpretation: dict[str, object] | None
    created_at: datetime


@dataclass(frozen=True)
class SearchRunListPage:
    runs: tuple[SearchRunView, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class SearchRunDetail:
    run: SearchRunView
    hits: tuple[SearchHitSnapshotView, ...]
    next_cursor: str | None
    total: int
    sorted_by: str
    left_relevance_order: bool


@dataclass(frozen=True)
class _SearchConfig:
    version_id: uuid.UUID
    candidate: CandidateConfiguration
    prompt: str
    prompt_version_id: str
    prompt_sha256: str
    schema: dict[str, object]
    schema_id: str
    schema_sha256: str
    catalog_asset: manifest.RequirementSchemaAsset


def normalize_utterance(raw: str) -> str:
    """Apply NFC and LF normalization without truncating or stripping."""
    normalized = unicodedata.normalize("NFC", raw)
    return normalized.replace("\r\n", "\n").replace("\r", "\n")


def validate_utterance(raw: str) -> str:
    normalized = normalize_utterance(raw)
    if not normalized.strip():
        raise InvalidUtteranceError
    if len(normalized) > MAX_UTTERANCE_CHARACTERS:
        raise InvalidUtteranceError
    return normalized


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _idempotency_fingerprint(
    utterance: str,
    configuration_version_id: uuid.UUID,
    search_contract_version: str,
) -> str:
    return _sha256(f"{utterance}\0{configuration_version_id}\0{search_contract_version}")


async def _load_search_config(session: AsyncSession) -> _SearchConfig:
    pointer = (
        await session.execute(
            select(LlmConfigurationCurrent).where(LlmConfigurationCurrent.singleton)
        )
    ).scalar_one()
    version = (
        await session.execute(
            select(LlmConfigurationVersion).where(LlmConfigurationVersion.id == pointer.version_id)
        )
    ).scalar_one()
    parsing_binding = (
        await session.execute(
            select(LlmConfigurationCallBinding).where(
                LlmConfigurationCallBinding.configuration_version_id == version.id,
                LlmConfigurationCallBinding.call_type == CALL_TYPE_JOB_REQUIREMENT_PARSING,
            )
        )
    ).scalar_one_or_none()
    search_binding = (
        await session.execute(
            select(LlmConfigurationCallBinding).where(
                LlmConfigurationCallBinding.configuration_version_id == version.id,
                LlmConfigurationCallBinding.call_type == CALL_TYPE_SEARCH_INTERPRETATION,
            )
        )
    ).scalar_one_or_none()
    prompt_version_id = (
        manifest.SEARCH_INTERPRETATION_PROMPT_V1.id
        if search_binding is None
        else search_binding.prompt_version_id
    )
    search_timeout = (
        DEFAULT_SEARCH_TIMEOUT_SECONDS
        if search_binding is None
        else search_binding.request_timeout_seconds
    )
    prompt = (
        await session.execute(select(PromptVersion).where(PromptVersion.id == prompt_version_id))
    ).scalar_one()
    schema_version = (
        await session.execute(
            select(SearchInterpretationSchemaVersion).where(
                SearchInterpretationSchemaVersion.id == prompt.output_schema_version_id
            )
        )
    ).scalar_one()
    candidate = CandidateConfiguration(
        model=version.model,
        temperature=float(version.temperature),
        max_output_tokens=version.max_output_tokens,
        input_character_limit=version.input_character_limit,
        bindings=(
            CallTypeBinding(
                call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                prompt_version_id=(
                    version.prompt_version_id
                    if parsing_binding is None
                    else parsing_binding.prompt_version_id
                ),
                request_timeout_seconds=(
                    version.request_timeout_seconds
                    if parsing_binding is None
                    else parsing_binding.request_timeout_seconds
                ),
            ),
            CallTypeBinding(
                call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                prompt_version_id=prompt_version_id,
                request_timeout_seconds=search_timeout,
            ),
        ),
    )
    return _SearchConfig(
        version_id=version.id,
        candidate=candidate,
        prompt=prompt.content,
        prompt_version_id=prompt.id,
        prompt_sha256=prompt.sha256,
        schema=schema_version.schema_json,
        schema_id=schema_version.id,
        schema_sha256=schema_version.sha256,
        catalog_asset=manifest.schema_asset(prompt.compatible_schema_version_id),
    )


def _hard_conditions(interpretation: dict[str, object]) -> tuple[HardCondition, ...]:
    raw = interpretation.get("hard_conditions", [])
    if not isinstance(raw, list):
        return ()
    conditions: list[HardCondition] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        condition = cast("dict[str, object]", item)
        if "field" not in condition or "operator" not in condition or "value" not in condition:
            continue
        conditions.append(
            HardCondition(
                field=str(condition["field"]),
                operator=str(condition["operator"]),
                value=cast("HardConditionValue", condition["value"]),
            )
        )
    return tuple(conditions)


async def run_search(  # noqa: PLR0915
    *,
    settings: AppSettings,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    utterance: str,
    idempotency_key: str,
) -> SearchRunView:
    """Create and execute one natural-language search run within the request."""
    normalized = validate_utterance(utterance)
    key_ring = _load_key_ring(settings)
    openrouter_adapter = _openrouter_adapter(settings)
    search_adapter = search_base_adapter_from_settings(settings)
    app_engine = create_engine_from_settings(settings)
    app_factory = create_session_factory(app_engine)
    sync_engine = create_engine_from_settings(settings, database_role=TALENT_SYNC_DATABASE_ROLE)
    sync_factory = create_session_factory(sync_engine)
    try:
        async with app_factory() as session:
            await tenant_context.set_tenant_context(session, tenant_id)
            config = await _load_search_config(session)
        fingerprint = _idempotency_fingerprint(
            normalized,
            config.version_id,
            settings.search_base_contract_version,
        )
        existing = await _find_run_by_idempotency_key(app_factory, tenant_id, idempotency_key)
        if existing is not None:
            if existing.idempotency_fingerprint == fingerprint:
                return await _load_run_view(app_factory, tenant_id, existing.id)
            await _audit_rejected(
                app_factory,
                tenant_id,
                actor_user_id,
                idempotency_key,
                IDEMPOTENCY_CONFLICT_DETAIL,
            )
            raise SearchIdempotencyConflictError
        await _enforce_rate_limits(
            app_factory,
            tenant_id,
            actor_user_id,
            idempotency_key,
            settings.search_run_creation_limit_per_hour,
        )
        run_id = await _create_run(
            app_factory,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            utterance=normalized,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            configuration_version_id=config.version_id,
            search_contract_version=settings.search_base_contract_version,
        )
        call_id = await _prepare_call(
            app_factory,
            tenant_id=tenant_id,
            run_id=run_id,
            config=config,
            utterance=normalized,
        )
        started_ns = time.monotonic_ns()
        try:
            result = await openrouter_adapter.generate_search_interpretation(
                config.candidate,
                system_prompt=config.prompt,
                schema=config.schema,
                utterance=normalized,
            )
        except OpenRouterAdapterError as error:
            _ = await llm_call_audit_service.persist_call_response(
                app_factory,
                call_id=call_id,
                key_ring=key_ring,
                requested_outcome="outcome_unknown" if error.outcome_unknown else "failed",
                category=error.category,
                exchange=error.exchange,
                result=None,
                duration_ms=_elapsed_ms(started_ns),
                tenant_id=tenant_id,
            )
            await _mark_failed(
                app_factory, tenant_id, actor_user_id, run_id, "interpretation_error"
            )
            return await _load_run_view(app_factory, tenant_id, run_id)
        _ = await llm_call_audit_service.persist_call_response(
            app_factory,
            call_id=call_id,
            key_ring=key_ring,
            requested_outcome="succeeded",
            category="",
            exchange=result.exchange,
            result=result,
            duration_ms=_elapsed_ms(started_ns),
            tenant_id=tenant_id,
        )
        try:
            interpretation = validate_search_interpretation(
                result.content,
                schema=config.schema,
                catalog_asset=config.catalog_asset,
            )
        except SearchInterpretationValidationError:
            await _mark_failed(
                app_factory, tenant_id, actor_user_id, run_id, "interpretation_invalid"
            )
            return await _load_run_view(app_factory, tenant_id, run_id)
        has_research_topic = bool(str(interpretation["research_topic_query"]).strip())
        await _store_interpretation(
            app_factory,
            tenant_id,
            run_id,
            interpretation=interpretation,
            has_research_topic=has_research_topic,
        )
        try:
            reservation = await _reserve(app_factory, tenant_id, run_id)
        except usage_service.QuotaExceededError:
            await _mark_failed(app_factory, tenant_id, actor_user_id, run_id, "quota_exceeded")
            raise SearchQuotaExceededError(run_id) from None
        try:
            search_result = await search_adapter.search_talent(
                _hard_conditions(interpretation),
                research_topic_query=str(interpretation["research_topic_query"]),
                hit_limit=MAX_SEARCH_HIT_LIMIT,
            )
        except SearchBaseAdapterError as error:
            await _release_reservation(app_factory, tenant_id, reservation.reservation_id)
            failure_reason = (
                "search_base_timeout" if error.category == "timeout" else "search_base_error"
            )
            await _mark_failed(app_factory, tenant_id, actor_user_id, run_id, failure_reason)
            return await _load_run_view(app_factory, tenant_id, run_id)
        local_ids = await _sync_local_talents(
            sync_factory,
            search_result.hits,
            search_result.data_version,
        )
        await _finalize_success(
            app_factory,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            run_id=run_id,
            reservation_id=reservation.reservation_id,
            hits=search_result.hits,
            data_version=search_result.data_version,
            request_id=search_result.request_id,
            local_ids=local_ids,
        )
        return await _load_run_view(app_factory, tenant_id, run_id)
    finally:
        await app_engine.dispose()
        await sync_engine.dispose()


async def list_runs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    cursor: str | None,
    limit: int,
) -> SearchRunListPage:
    offset = _parse_cursor(cursor)
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(NaturalLanguageSearchRun)
                .where(NaturalLanguageSearchRun.tenant_id == tenant_id)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await session.execute(
                select(NaturalLanguageSearchRun)
                .where(NaturalLanguageSearchRun.tenant_id == tenant_id)
                .order_by(NaturalLanguageSearchRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    next_cursor = None if offset + len(rows) >= total else str(offset + limit)
    return SearchRunListPage(
        runs=tuple(_run_view_from_model(row) for row in rows),
        next_cursor=next_cursor,
    )


async def get_run(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    sort: str | None,
    cursor: str | None,
    limit: int,
) -> SearchRunDetail:
    resolved_sort = _resolve_sort(sort)
    offset = _parse_cursor(cursor)
    run = (
        await session.execute(
            select(NaturalLanguageSearchRun).where(
                NaturalLanguageSearchRun.id == run_id,
                NaturalLanguageSearchRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise SearchRunNotFoundError
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(SearchHitSnapshot)
                .where(SearchHitSnapshot.search_run_id == run_id)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await session.execute(
                select(SearchHitSnapshot)
                .where(SearchHitSnapshot.search_run_id == run_id)
                .order_by(*_order_by_for_sort(resolved_sort))
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    next_cursor = None if offset + len(rows) >= total else str(offset + limit)
    return SearchRunDetail(
        run=_run_view_from_model(run),
        hits=tuple(_hit_view_from_model(row) for row in rows),
        next_cursor=next_cursor,
        total=total,
        sorted_by=resolved_sort,
        left_relevance_order=run.has_research_topic and resolved_sort != SORT_KEY_SEMANTIC,
    )


def _resolve_sort(sort: str | None) -> str:
    if sort is None:
        return SORT_KEY_SEMANTIC
    if sort not in SORT_KEYS:
        raise InvalidSortError
    return sort


def _order_by_for_sort(sort: str) -> tuple[ColumnElement[Any], ...]:  # noqa: PLR0911  # pyright: ignore[reportExplicitAny]
    tiebreak = SearchHitSnapshot.sort_position.asc()
    if sort == SORT_KEY_SEMANTIC:
        return (SearchHitSnapshot.semantic_score.desc().nullslast(), tiebreak)
    if sort == "h_index":
        return (SearchHitSnapshot.h_index.desc(), tiebreak)
    if sort == "total_citations":
        return (SearchHitSnapshot.total_citations.desc(), tiebreak)
    if sort == "qs_top200_rank":
        return (SearchHitSnapshot.qs_top200_rank.asc().nullslast(), tiebreak)
    if sort == "world_top500_rank":
        return (SearchHitSnapshot.world_top500_rank.asc().nullslast(), tiebreak)
    if sort == "display_name":
        return (SearchHitSnapshot.display_name.asc(), tiebreak)
    if sort == "current_affiliation":
        return (SearchHitSnapshot.current_affiliation.asc(), tiebreak)
    if sort == "country":
        return (SearchHitSnapshot.country.asc(), tiebreak)
    if sort == "chinese_identity":
        return (SearchHitSnapshot.chinese_identity.asc(), tiebreak)
    raise InvalidSortError


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        parsed = int(cursor)
    except ValueError:
        return 0
    return max(parsed, 0)


def _load_key_ring(settings: AppSettings) -> llm_call_audit_service.RawResponseKeyRing:
    return llm_call_audit_service.RawResponseKeyRing.parse(
        settings.llm_raw_response_keys.get_secret_value(),
        settings.llm_raw_response_active_key_id,
    )


def _openrouter_adapter(settings: AppSettings) -> OpenRouterAdapter:
    api_key = (
        ""
        if settings.openrouter_api_key is None
        else settings.openrouter_api_key.get_secret_value()
    )
    return OpenRouterAdapter(
        OpenRouterClientConfig(
            api_key=api_key,
            base_url=settings.openrouter_base_url,
            site_url=settings.openrouter_site_url,
            site_name=settings.openrouter_site_name,
        )
    )


def _elapsed_ms(started_ns: int) -> int:
    return max((time.monotonic_ns() - started_ns) // 1_000_000, 0)


async def _find_run_by_idempotency_key(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    idempotency_key: str,
) -> NaturalLanguageSearchRun | None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        return (
            await session.execute(
                select(NaturalLanguageSearchRun).where(
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                    NaturalLanguageSearchRun.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()


async def _enforce_rate_limits(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    creation_limit_per_hour: int,
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        created_in_window = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(NaturalLanguageSearchRun)
                    .where(
                        NaturalLanguageSearchRun.tenant_id == tenant_id,
                        NaturalLanguageSearchRun.created_at
                        >= datetime.now(UTC) - timedelta(hours=1),
                    )
                )
            ).scalar_one()
        )
        if created_in_window >= creation_limit_per_hour:
            await _audit_rejected_on(
                session, tenant_id, actor_user_id, idempotency_key, CREATION_RATE_LIMITED_DETAIL
            )
            await session.commit()
            raise SearchCreationRateLimitedError
        in_progress = (
            await session.execute(
                select(NaturalLanguageSearchRun.id).where(
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                    NaturalLanguageSearchRun.status == SEARCH_RUN_STATUS_IN_PROGRESS,
                )
            )
        ).scalar_one_or_none()
        if in_progress is not None:
            await _audit_rejected_on(
                session, tenant_id, actor_user_id, idempotency_key, SEARCH_IN_PROGRESS_DETAIL
            )
            await session.commit()
            raise SearchInProgressError


async def _audit_rejected(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    detail: str,
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        await _audit_rejected_on(session, tenant_id, actor_user_id, idempotency_key, detail)
        await session.commit()


async def _audit_rejected_on(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    detail: str,
) -> None:
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=AUDIT_ACTION_REJECTED,
        target_type=AUDIT_REJECTED_TARGET_TYPE,
        target_id=idempotency_key,
        result=tenant_audit_service.AUDIT_RESULT_FAILURE,
        detail=detail,
    )


async def _create_run(  # noqa: PLR0913
    app_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    utterance: str,
    idempotency_key: str,
    idempotency_fingerprint: str,
    configuration_version_id: uuid.UUID,
    search_contract_version: str,
) -> uuid.UUID:
    run = NaturalLanguageSearchRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        status=SEARCH_RUN_STATUS_IN_PROGRESS,
        utterance=utterance,
        utterance_sha256=_sha256(utterance),
        utterance_length=len(utterance),
        idempotency_key=idempotency_key,
        idempotency_fingerprint=idempotency_fingerprint,
        llm_configuration_version_id=configuration_version_id,
        search_contract_version=search_contract_version,
    )
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        session.add(run)
        await session.commit()
    return run.id


async def _prepare_call(
    app_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    config: _SearchConfig,
    utterance: str,
) -> uuid.UUID:
    payload = OpenRouterAdapter(
        OpenRouterClientConfig(api_key="not-persisted")
    ).build_search_interpretation_payload(
        config.candidate,
        system_prompt=config.prompt,
        schema=config.schema,
        utterance=utterance,
    )
    request_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    call = LlmCallRecord(
        id=uuid.uuid4(),
        scope="tenant",
        tenant_id=tenant_id,
        call_type=CALL_TYPE_SEARCH_INTERPRETATION,
        platform_attempt_id=None,
        job_requirement_parsing_task_id=None,
        search_run_id=run_id,
        configuration_version_id=config.version_id,
        input_snapshot_id=None,
        correlation_call_id=None,
        request_number=1,
        model=config.candidate.model,
        prompt_version_id=config.prompt_version_id,
        prompt_sha256=config.prompt_sha256,
        requirement_schema_version_id=config.schema_id,
        requirement_schema_sha256=config.schema_sha256,
        input_sources_summary={
            "search_utterance": {"characters": len(utterance), "sha256": _sha256(utterance)}
        },
        input_sha256=_sha256(utterance),
        input_length=len(utterance),
        parameters={
            "max_output_tokens": config.candidate.max_output_tokens,
            "temperature": config.candidate.temperature,
        },
        request_hash=request_hash,
    )
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        session.add(call)
        await session.flush()
        call_id = call.id
        await session.commit()
    return call_id


async def _mark_failed(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    run_id: uuid.UUID,
    failure_reason: NaturalLanguageSearchRunFailureReason,
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        run = (
            await session.execute(
                select(NaturalLanguageSearchRun).where(
                    NaturalLanguageSearchRun.id == run_id,
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        run.status = SEARCH_RUN_STATUS_FAILED
        run.failure_reason = failure_reason
        tenant_audit_service.record_event(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=AUDIT_ACTION_FAILED,
            target_type=AUDIT_TARGET_TYPE,
            target_id=str(run_id),
            result=tenant_audit_service.AUDIT_RESULT_FAILURE,
            detail=failure_reason,
        )
        await session.commit()


async def _store_interpretation(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    interpretation: dict[str, object],
    has_research_topic: bool,
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        run = (
            await session.execute(
                select(NaturalLanguageSearchRun).where(
                    NaturalLanguageSearchRun.id == run_id,
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        run.search_interpretation = interpretation
        run.has_research_topic = has_research_topic
        await session.commit()


async def _reserve(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> usage_service.ReservationView:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        return await usage_service.reserve(
            session,
            tenant_id=tenant_id,
            metric="searches",
            amount=1,
            idempotency_key=f"search-run:{run_id}",
            reference_type=AUDIT_TARGET_TYPE,
            reference_id=str(run_id),
        )


async def _release_reservation(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        _ = await usage_service.release(session, tenant_id=tenant_id, reservation_id=reservation_id)


async def _sync_local_talents(
    sync_factory: async_sessionmaker[AsyncSession],
    hits: tuple[SearchHit, ...],
    data_version: str,
) -> list[tuple[int, SearchHit, uuid.UUID]]:
    results: list[tuple[int, SearchHit, uuid.UUID]] = []
    async with sync_factory() as session:
        for position, hit in enumerate(hits):
            view = await talent_identity_service.upsert_person(session, hit.person, data_version)
            results.append((position, hit, view.id))
    return results


async def _finalize_success(  # noqa: PLR0913
    app_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    run_id: uuid.UUID,
    reservation_id: uuid.UUID,
    hits: tuple[SearchHit, ...],
    data_version: str,
    request_id: str,
    local_ids: list[tuple[int, SearchHit, uuid.UUID]],
) -> None:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        run = (
            await session.execute(
                select(NaturalLanguageSearchRun).where(
                    NaturalLanguageSearchRun.id == run_id,
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        local_by_position = {position: (hit, local_id) for position, hit, local_id in local_ids}
        for position, hit in enumerate(hits):
            entry = local_by_position.get(position)
            if entry is None:
                continue
            _, local_talent_id = entry
            session.add(
                SearchHitSnapshot(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    search_run_id=run_id,
                    local_talent_id=local_talent_id,
                    canonical_person_id=hit.person.canonical_person_id,
                    display_name=hit.person.display_name,
                    current_affiliation=hit.person.current_affiliation,
                    country=hit.person.country,
                    chinese_identity=hit.person.chinese_identity,
                    h_index=hit.person.h_index,
                    total_citations=hit.person.total_citations,
                    qs_top200_rank=hit.person.qs_top200_rank,
                    world_top500_rank=hit.person.world_top500_rank,
                    has_contact=hit.person.has_contact,
                    data_version=data_version,
                    hit_publications=[
                        {
                            "publication_id": publication.publication_id,
                            "title": publication.title,
                            "year": publication.year,
                            "venue": publication.venue,
                            "snippet": publication.snippet,
                        }
                        for publication in hit.hit_publications
                    ],
                    semantic_score=hit.semantic_score,
                    sort_position=position,
                )
            )
        run.status = SEARCH_RUN_STATUS_SUCCEEDED
        run.failure_reason = None
        run.data_version = data_version
        run.request_id = request_id
        run.usage_reservation_id = reservation_id
        tenant_audit_service.record_event(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=AUDIT_ACTION_SUCCEEDED,
            target_type=AUDIT_TARGET_TYPE,
            target_id=str(run_id),
            result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
            detail=f"hits={len(local_ids)};data_version={data_version}",
        )
        await session.commit()
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        _ = await usage_service.confirm(session, tenant_id=tenant_id, reservation_id=reservation_id)


async def _load_run_view(
    app_factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> SearchRunView:
    async with app_factory() as session:
        await tenant_context.set_tenant_context(session, tenant_id)
        run = (
            await session.execute(
                select(NaturalLanguageSearchRun).where(
                    NaturalLanguageSearchRun.id == run_id,
                    NaturalLanguageSearchRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        return _run_view_from_model(run)


def _run_view_from_model(run: NaturalLanguageSearchRun) -> SearchRunView:
    return SearchRunView(
        id=run.id,
        status=run.status,
        failure_reason=run.failure_reason,
        utterance=run.utterance,
        utterance_length=run.utterance_length,
        idempotency_key=run.idempotency_key,
        llm_configuration_version_id=run.llm_configuration_version_id,
        search_contract_version=run.search_contract_version,
        data_version=run.data_version,
        request_id=run.request_id,
        has_research_topic=run.has_research_topic,
        search_interpretation=run.search_interpretation,
        created_at=run.created_at,
    )


def _hit_view_from_model(snapshot: SearchHitSnapshot) -> SearchHitSnapshotView:
    return SearchHitSnapshotView(
        id=snapshot.id,
        local_talent_id=snapshot.local_talent_id,
        canonical_person_id=snapshot.canonical_person_id,
        display_name=snapshot.display_name,
        current_affiliation=snapshot.current_affiliation,
        country=snapshot.country,
        chinese_identity=snapshot.chinese_identity,
        h_index=snapshot.h_index,
        total_citations=snapshot.total_citations,
        qs_top200_rank=snapshot.qs_top200_rank,
        world_top500_rank=snapshot.world_top500_rank,
        has_contact=snapshot.has_contact,
        data_version=snapshot.data_version,
        hit_publications=snapshot.hit_publications,
        semantic_score=snapshot.semantic_score,
        sort_position=snapshot.sort_position,
    )
