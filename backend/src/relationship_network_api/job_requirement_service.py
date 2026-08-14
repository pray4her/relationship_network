from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, final

from sqlalchemy import case, func, insert, select
from sqlalchemy.exc import IntegrityError

from relationship_network_api import (
    job_requirement_draft_service,
    tenant_audit_service,
    tenant_context,
)
from relationship_network_api.job_requirement_validation import (
    NormalizedSource,
    normalize_sent_text,
    sha256_text,
    snapshot_content_sha256,
)
from relationship_network_api.job_service import JobNotFoundError
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    JOB_STATUS_ARCHIVED,
    Job,
    JobMaterial,
    JobRequirementDraft,
    JobRequirementInputSnapshot,
    JobRequirementInputSource,
    JobRequirementParsingTask,
    JobRequirementParsingTaskEvent,
    JobRequirementSchemaVersion,
    JobRequirementVersion,
    LlmConfigurationCurrent,
    LlmConfigurationVersion,
    Tenant,
    TenantOutboxEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

JOB_DESCRIPTION_SOURCE_ID: Final = "job-description"
JOB_MATERIAL_SOURCE_PREFIX: Final = "job-material:"
OUTBOX_TOPIC: Final = "job_requirement_parsing.process"
ACTION_CREATE: Final = "job_requirement_parsing.create"
ACTION_RESULT: Final = "job_requirement_parsing.finish"
ACTION_CANCEL: Final = "job_requirement_parsing.cancel"
TARGET_TYPE: Final = "job_requirement_parsing_task"

JOB_ARCHIVED: Final = "job_archived"
SOURCE_NOT_FOUND: Final = "requirement_source_not_found"
MATERIAL_UNAVAILABLE: Final = "requirement_material_unavailable"
EMPTY_INPUT: Final = "requirement_input_empty"
EMPTY_MATERIAL_CORRECTION: Final = "requirement_material_correction_empty"
INPUT_TOO_LARGE: Final = "requirement_input_too_large"
TASK_EXISTS: Final = "requirement_task_exists"
DRAFT_EXISTS: Final = "requirement_draft_exists"
DRAFT_REPLACEMENT_CONFLICT: Final = "requirement_draft_replacement_conflict"
CONFIGURATION_NOT_READY: Final = "requirement_configuration_not_ready"
IDEMPOTENCY_CONFLICT: Final = "idempotency_conflict"
CREATION_RATE_LIMITED: Final = "requirement_creation_rate_limited"
TASK_NOT_FOUND: Final = "requirement_task_not_found"
TASK_TERMINAL: Final = "requirement_task_terminal"
INVALID_LAST_EVENT_ID: Final = "invalid_last_event_id"
CREATION_LIMIT_PER_HOUR: Final = 20

NONTERMINAL_STATUSES: Final = ("queued", "running", "retry_scheduled", "cancel_requested")


@final
class RequirementGenerationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@final
@dataclass(frozen=True)
class RequirementSourceSubmission:
    source_id: str
    corrected_text: str


@final
@dataclass(frozen=True)
class RequirementSourceView:
    source_id: str
    source_kind: str
    material_id: uuid.UUID | None
    label: str
    original_text: str
    scan_status: str
    created_at: datetime | None


@final
@dataclass(frozen=True)
class RequirementTaskView:
    id: uuid.UUID
    status: str
    error_code: str | None
    input_snapshot_id: uuid.UUID
    configuration_version_id: uuid.UUID
    replaces_draft_id: uuid.UUID | None
    external_call_count: int
    structured_invalid_count: int
    created_by: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    next_attempt_at: datetime | None
    updated_at: datetime


@final
@dataclass(frozen=True)
class RequirementTaskEventView:
    sequence_number: int
    task_id: uuid.UUID
    status: str
    error_code: str | None
    retryable: bool
    next_attempt_at: datetime | None
    created_at: datetime


@final
@dataclass(frozen=True)
class RequirementDraftView:
    id: uuid.UUID
    task_id: uuid.UUID | None
    input_snapshot_id: uuid.UUID | None
    source_version_id: uuid.UUID | None
    requirement_schema_version_id: str
    status: str
    revision: int
    result: dict[str, object]
    updated_by: uuid.UUID | None
    status_changed_at: datetime
    read_only_reason: str | None
    field_catalog: dict[str, object]
    chinese_identity_values: list[str]
    created_at: datetime
    updated_at: datetime
    pending_upgrade_items: list[dict[str, object]] = field(default_factory=list)


@final
@dataclass(frozen=True)
class RequirementVersionSummaryView:
    id: uuid.UUID
    version_number: int
    requirement_schema_version_id: str
    draft_id: uuid.UUID
    source_version_id: uuid.UUID | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime
    created_at: datetime
    is_current: bool


@final
@dataclass(frozen=True)
class RequirementVersionView:
    id: uuid.UUID
    version_number: int
    requirement_schema_version_id: str
    result: dict[str, object]
    draft_id: uuid.UUID
    input_snapshot_id: uuid.UUID | None
    source_version_id: uuid.UUID | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime
    created_at: datetime
    is_current: bool


@final
@dataclass(frozen=True)
class RequirementWorkspaceView:
    configuration_ready: bool
    input_character_limit: int
    sources: list[RequirementSourceView]
    task: RequirementTaskView | None
    draft: RequirementDraftView | None
    current_version: RequirementVersionView | None
    versions: list[RequirementVersionSummaryView]
    legacy_requirement_exempt: bool
    matching_blocked: bool


async def load_workspace(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> RequirementWorkspaceView:
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    configuration = await _current_configuration(session)
    materials = list(
        (
            await session.execute(
                select(JobMaterial)
                .where(JobMaterial.tenant_id == tenant_id, JobMaterial.job_id == job_id)
                .order_by(JobMaterial.created_at, JobMaterial.id)
            )
        )
        .scalars()
        .all()
    )
    task = (
        await session.execute(
            select(JobRequirementParsingTask)
            .where(
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.job_id == job_id,
            )
            .order_by(
                case(
                    (JobRequirementParsingTask.status.in_(NONTERMINAL_STATUSES), 0),
                    else_=1,
                ),
                JobRequirementParsingTask.created_at.desc(),
                JobRequirementParsingTask.id.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    draft = (
        await session.execute(
            select(JobRequirementDraft)
            .where(
                JobRequirementDraft.tenant_id == tenant_id,
                JobRequirementDraft.job_id == job_id,
                JobRequirementDraft.status == "editable",
            )
            .order_by(JobRequirementDraft.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    draft_view: RequirementDraftView | None = None
    if draft is not None:
        schema = (
            await session.execute(
                select(JobRequirementSchemaVersion).where(
                    JobRequirementSchemaVersion.id == draft.requirement_schema_version_id
                )
            )
        ).scalar_one()
        reason = await job_requirement_draft_service.read_only_reason(
            session,
            job=job,
            draft=draft,
        )
        pending = await job_requirement_draft_service.pending_schema_upgrade_items(
            session,
            tenant_id=tenant_id,
            draft_id=draft.id,
        )
        draft_view = _draft_view(
            draft,
            schema=schema,
            read_only_reason=reason,
            pending_upgrade_items=pending,
        )
    versions = list(
        (
            await session.execute(
                select(JobRequirementVersion)
                .where(
                    JobRequirementVersion.tenant_id == tenant_id,
                    JobRequirementVersion.job_id == job_id,
                )
                .order_by(
                    JobRequirementVersion.version_number.desc(),
                    JobRequirementVersion.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    current_id = job.current_requirement_version_id
    current_version: RequirementVersionView | None = None
    version_summaries: list[RequirementVersionSummaryView] = []
    for version in versions:
        is_current = version.id == current_id
        version_summaries.append(
            RequirementVersionSummaryView(
                id=version.id,
                version_number=version.version_number,
                requirement_schema_version_id=version.requirement_schema_version_id,
                draft_id=version.draft_id,
                source_version_id=version.source_version_id,
                confirmed_by=version.confirmed_by,
                confirmed_at=version.confirmed_at,
                created_at=version.created_at,
                is_current=is_current,
            )
        )
        if is_current:
            current_version = RequirementVersionView(
                id=version.id,
                version_number=version.version_number,
                requirement_schema_version_id=version.requirement_schema_version_id,
                result=version.result_json,
                draft_id=version.draft_id,
                input_snapshot_id=version.input_snapshot_id,
                source_version_id=version.source_version_id,
                confirmed_by=version.confirmed_by,
                confirmed_at=version.confirmed_at,
                created_at=version.created_at,
                is_current=True,
            )
    matching_blocked = (
        job.status != JOB_STATUS_ARCHIVED and current_id is None and job.legacy_requirement_exempt
    )
    return RequirementWorkspaceView(
        configuration_ready=_configuration_ready(configuration),
        input_character_limit=configuration.input_character_limit,
        sources=[
            RequirementSourceView(
                source_id=JOB_DESCRIPTION_SOURCE_ID,
                source_kind="job-description",
                material_id=None,
                label="职位描述",
                original_text=job.description,
                scan_status="content_checked",
                created_at=None,
            ),
            *[
                RequirementSourceView(
                    source_id=f"{JOB_MATERIAL_SOURCE_PREFIX}{material.id}",
                    source_kind="job-material",
                    material_id=material.id,
                    label=material.original_filename,
                    original_text=material.extracted_text,
                    scan_status=material.scan_status,
                    created_at=material.created_at,
                )
                for material in materials
            ],
        ],
        task=None if task is None else _task_view(task),
        draft=draft_view,
        current_version=current_version,
        versions=version_summaries,
        legacy_requirement_exempt=job.legacy_requirement_exempt,
        matching_blocked=matching_blocked,
    )


async def create_parsing_task(  # noqa: C901, PLR0912, PLR0913, PLR0915
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    submissions: list[RequirementSourceSubmission],
) -> RequirementTaskView:
    _ = (
        await session.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
    ).scalar_one()
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id, for_update=True)
    configuration = await _current_configuration(session)
    if not _configuration_ready(configuration):
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=CONFIGURATION_NOT_READY,
        )
    by_id: dict[str, str] = {}
    for submission in submissions:
        if submission.source_id in by_id:
            await _reject(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                job_id=job_id,
                code=SOURCE_NOT_FOUND,
            )
        by_id[submission.source_id] = submission.corrected_text
    materials = list(
        (
            await session.execute(
                select(JobMaterial)
                .where(JobMaterial.tenant_id == tenant_id, JobMaterial.job_id == job_id)
                .order_by(JobMaterial.created_at, JobMaterial.id)
            )
        )
        .scalars()
        .all()
    )
    known_ids = {
        JOB_DESCRIPTION_SOURCE_ID,
        *[f"{JOB_MATERIAL_SOURCE_PREFIX}{m.id}" for m in materials],
    }
    if not by_id or not set(by_id).issubset(known_ids):
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=EMPTY_INPUT if not by_id else SOURCE_NOT_FOUND,
        )
    prepared: list[tuple[str, str, uuid.UUID | None, str, str]] = []
    description_correction = by_id.get(JOB_DESCRIPTION_SOURCE_ID)
    if description_correction is not None:
        normalized = normalize_sent_text(description_correction)
        if not normalized.strip():
            await _reject(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                job_id=job_id,
                code=EMPTY_INPUT,
            )
        prepared.append(
            (
                JOB_DESCRIPTION_SOURCE_ID,
                "job-description",
                None,
                job.description,
                description_correction,
            )
        )
    for material in materials:
        source_id = f"{JOB_MATERIAL_SOURCE_PREFIX}{material.id}"
        correction = by_id.get(source_id)
        if correction is None:
            continue
        if material.scan_status != "content_checked":
            await _reject(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                job_id=job_id,
                code=MATERIAL_UNAVAILABLE,
            )
        if not normalize_sent_text(correction).strip():
            await _reject(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                job_id=job_id,
                code=EMPTY_MATERIAL_CORRECTION,
            )
        prepared.append(
            (source_id, "job-material", material.id, material.extracted_text, correction)
        )
    normalized_sources = [
        NormalizedSource(source_id=source_id, sent_text=normalize_sent_text(correction))
        for source_id, _kind, _material_id, _original, correction in prepared
    ]
    total_characters = sum(len(source.sent_text) for source in normalized_sources)
    if total_characters == 0:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=EMPTY_INPUT,
        )
    if total_characters > configuration.input_character_limit:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=INPUT_TOO_LARGE,
        )
    if job.status == JOB_STATUS_ARCHIVED:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=JOB_ARCHIVED,
        )
    current_draft = (
        await session.execute(
            select(JobRequirementDraft)
            .where(
                JobRequirementDraft.tenant_id == tenant_id,
                JobRequirementDraft.job_id == job_id,
                JobRequirementDraft.status == "editable",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    existing_idempotent = (
        await session.execute(
            select(JobRequirementParsingTask).where(
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing_idempotent is not None:
        existing_request_sha256 = _effective_request_sha256(
            job_id=job_id,
            configuration_version_id=existing_idempotent.configuration_version_id,
            sources=normalized_sources,
            replaces_draft_id=existing_idempotent.replaces_draft_id,
            replaces_draft_revision=existing_idempotent.replaces_draft_revision,
        )
        if existing_idempotent.effective_request_sha256 == existing_request_sha256:
            return _task_view(existing_idempotent)
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=IDEMPOTENCY_CONFLICT,
        )
    effective_request_sha256 = _effective_request_sha256(
        job_id=job_id,
        configuration_version_id=configuration.id,
        sources=normalized_sources,
        replaces_draft_id=None if current_draft is None else current_draft.id,
        replaces_draft_revision=None if current_draft is None else current_draft.revision,
    )
    created_in_window = int(
        (
            await session.execute(
                select(func.count())
                .select_from(JobRequirementParsingTask)
                .where(
                    JobRequirementParsingTask.tenant_id == tenant_id,
                    JobRequirementParsingTask.created_at >= datetime.now(UTC) - timedelta(hours=1),
                )
            )
        ).scalar_one()
    )
    if created_in_window >= CREATION_LIMIT_PER_HOUR:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=CREATION_RATE_LIMITED,
        )
    task_exists = (
        await session.execute(
            select(JobRequirementParsingTask.id).where(
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.job_id == job_id,
                JobRequirementParsingTask.status.in_(NONTERMINAL_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if task_exists is not None:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=TASK_EXISTS,
        )
    snapshot = JobRequirementInputSnapshot(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_id=job_id,
        configuration_version_id=configuration.id,
        total_characters=total_characters,
        content_sha256=snapshot_content_sha256(normalized_sources),
        created_by=actor_user_id,
    )
    task = JobRequirementParsingTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_id=job_id,
        input_snapshot_id=snapshot.id,
        configuration_version_id=configuration.id,
        idempotency_key=idempotency_key,
        effective_request_sha256=effective_request_sha256,
        replaces_draft_id=None if current_draft is None else current_draft.id,
        replaces_draft_revision=None if current_draft is None else current_draft.revision,
        status="queued",
        created_by=actor_user_id,
    )
    session.add(snapshot)
    for position, ((source_id, kind, material_id, original, correction), normalized) in enumerate(
        zip(prepared, normalized_sources, strict=True)
    ):
        session.add(
            JobRequirementInputSource(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                job_id=job_id,
                snapshot_id=snapshot.id,
                source_id=source_id,
                source_kind=kind,
                material_id=material_id,
                position=position,
                original_text=original,
                corrected_text=correction,
                sent_text=normalized.sent_text,
                original_sha256=sha256_text(original),
                sent_sha256=sha256_text(normalized.sent_text),
                unicode_characters=len(normalized.sent_text),
                edited_by=actor_user_id,
            )
        )
    session.add(task)
    session.add(
        JobRequirementParsingTaskEvent(
            task_id=task.id,
            sequence_number=1,
            tenant_id=tenant_id,
            event_type="queued",
            payload={},
        )
    )
    await enqueue_tenant_outbox(
        session,
        tenant_id=tenant_id,
        task_id=task.id,
        topic=OUTBOX_TOPIC,
        aggregate_id=task.id,
    )
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_CREATE,
        target_type=TARGET_TYPE,
        target_id=str(task.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"job={job_id};sources={len(prepared)};characters={total_characters}",
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        await _record_failure(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            code=TASK_EXISTS,
        )
        raise RequirementGenerationError(TASK_EXISTS) from error
    return _task_view(task)


async def enqueue_tenant_outbox(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    topic: str,
    aggregate_id: uuid.UUID,
    available_at: datetime | None = None,
) -> None:
    """Insert without implicit RETURNING so writers need no Outbox read privilege."""
    values: dict[str, object] = {
        "aggregate_id": aggregate_id,
        "id": uuid.uuid4(),
        "job_requirement_parsing_task_id": task_id,
        "tenant_id": tenant_id,
        "topic": topic,
    }
    if available_at is not None:
        values["available_at"] = available_at
    _ = await session.execute(insert(TenantOutboxEvent).inline().values(**values))


async def append_task_event(
    session: AsyncSession,
    *,
    task: JobRequirementParsingTask,
    payload: dict[str, object],
) -> JobRequirementParsingTaskEvent:
    await session.flush()
    sequence = (
        int(
            (
                await session.execute(
                    select(
                        func.coalesce(func.max(JobRequirementParsingTaskEvent.sequence_number), 0)
                    ).where(JobRequirementParsingTaskEvent.task_id == task.id)
                )
            ).scalar_one()
        )
        + 1
    )
    event = JobRequirementParsingTaskEvent(
        task_id=task.id,
        sequence_number=sequence,
        tenant_id=task.tenant_id,
        event_type=task.status,
        payload=payload,
    )
    session.add(event)
    return event


async def get_task(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    for_update: bool = False,
) -> RequirementTaskView:
    _ = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    statement = select(JobRequirementParsingTask).where(
        JobRequirementParsingTask.id == task_id,
        JobRequirementParsingTask.tenant_id == tenant_id,
        JobRequirementParsingTask.job_id == job_id,
    )
    if for_update:
        statement = statement.with_for_update()
    task = (await session.execute(statement)).scalar_one_or_none()
    if task is None:
        raise RequirementGenerationError(TASK_NOT_FOUND)
    return _task_view(task)


async def list_task_events(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    after_sequence: int,
) -> list[RequirementTaskEventView]:
    _ = await get_task(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        task_id=task_id,
    )
    events = list(
        (
            await session.execute(
                select(JobRequirementParsingTaskEvent)
                .where(
                    JobRequirementParsingTaskEvent.tenant_id == tenant_id,
                    JobRequirementParsingTaskEvent.task_id == task_id,
                    JobRequirementParsingTaskEvent.sequence_number > after_sequence,
                )
                .order_by(JobRequirementParsingTaskEvent.sequence_number)
            )
        )
        .scalars()
        .all()
    )
    return [_event_view(event) for event in events]


async def cancel_parsing_task(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> RequirementTaskView:
    _ = await _load_job(session, tenant_id=tenant_id, job_id=job_id, for_update=True)
    task = (
        await session.execute(
            select(JobRequirementParsingTask)
            .where(
                JobRequirementParsingTask.id == task_id,
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.job_id == job_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None:
        raise RequirementGenerationError(TASK_NOT_FOUND)
    if task.status == "cancelled":
        return _task_view(task)
    if task.status in {"succeeded", "failed"}:
        raise RequirementGenerationError(TASK_TERMINAL)
    if task.status == "cancel_requested":
        return _task_view(task)
    now = datetime.now(UTC)
    if task.status in {"queued", "retry_scheduled"}:
        task.status = "cancelled"
        task.completed_at = now
        task.next_attempt_at = None
    else:
        task.status = "cancel_requested"
    _ = await append_task_event(session, task=task, payload={})
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_CANCEL,
        target_type=TARGET_TYPE,
        target_id=str(task.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
    )
    await session.refresh(task)
    view = _task_view(task)
    await session.commit()
    return view


async def transition_task_for_job_archive(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Give archival priority over any nonterminal parsing task in the same transaction."""
    task = (
        await session.execute(
            select(JobRequirementParsingTask)
            .where(
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.job_id == job_id,
                JobRequirementParsingTask.status.in_(NONTERMINAL_STATUSES),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None or task.status == "cancel_requested":
        return
    if task.status == "running":
        task.status = "cancel_requested"
    else:
        task.status = "cancelled"
        task.completed_at = datetime.now(UTC)
        task.next_attempt_at = None
    _ = await append_task_event(session, task=task, payload={})


async def _current_configuration(session: AsyncSession) -> LlmConfigurationVersion:
    return (
        await session.execute(
            select(LlmConfigurationVersion)
            .join(
                LlmConfigurationCurrent,
                LlmConfigurationCurrent.version_id == LlmConfigurationVersion.id,
            )
            .where(LlmConfigurationCurrent.singleton)
        )
    ).scalar_one()


def _configuration_ready(configuration: LlmConfigurationVersion) -> bool:
    """Derive the task schema from the prompt bound to the current configuration.

    A configuration is ready only when its prompt is a deployed asset, the
    configuration's schema is exactly the prompt's declared compatible
    schema, and that schema ships an editor schema. There is no independent
    mutable schema pointer.
    """
    try:
        prompt_asset = manifest.prompt_asset(configuration.prompt_version_id)
        schema_asset = manifest.schema_asset(configuration.requirement_schema_version_id)
    except manifest.LlmAssetError:
        return False
    if schema_asset.editor_schema_id is None:
        return False
    return prompt_asset.compatible_schema_version_id == schema_asset.id


def _effective_request_sha256(
    *,
    job_id: uuid.UUID,
    configuration_version_id: uuid.UUID,
    sources: list[NormalizedSource],
    replaces_draft_id: uuid.UUID | None,
    replaces_draft_revision: int | None,
) -> str:
    canonical = {
        "configuration_version_id": str(configuration_version_id),
        "job_id": str(job_id),
        "replaces_draft_id": None if replaces_draft_id is None else str(replaces_draft_id),
        "replaces_draft_revision": replaces_draft_revision,
        "sources": [
            {
                "content_sha256": sha256_text(source.sent_text),
                "source_id": source.source_id,
            }
            for source in sources
        ],
    }
    serialized = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def _load_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    for_update: bool = False,
) -> Job:
    statement = select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    if for_update:
        statement = statement.with_for_update()
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError
    return job


async def _reject(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
    code: str,
) -> None:
    await session.rollback()
    await tenant_context.set_tenant_context(session, tenant_id)
    await _record_failure(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        job_id=job_id,
        code=code,
    )
    raise RequirementGenerationError(code)


async def _record_failure(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
    code: str,
) -> None:
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_CREATE,
        target_type="job",
        target_id=str(job_id),
        result=tenant_audit_service.AUDIT_RESULT_FAILURE,
        detail=code,
    )
    await session.commit()


def _task_view(task: JobRequirementParsingTask) -> RequirementTaskView:
    return RequirementTaskView(
        id=task.id,
        status=task.status,
        error_code=task.error_code,
        input_snapshot_id=task.input_snapshot_id,
        configuration_version_id=task.configuration_version_id,
        replaces_draft_id=task.replaces_draft_id,
        external_call_count=task.external_call_count,
        structured_invalid_count=task.structured_invalid_count,
        created_by=task.created_by,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        next_attempt_at=task.next_attempt_at,
        updated_at=task.updated_at,
    )


def _event_view(event: JobRequirementParsingTaskEvent) -> RequirementTaskEventView:
    error_code_raw = event.payload.get("error_code")
    retryable_raw = event.payload.get("retryable")
    next_attempt_raw = event.payload.get("next_attempt_at")
    next_attempt_at: datetime | None = None
    if isinstance(next_attempt_raw, str):
        try:
            next_attempt_at = datetime.fromisoformat(next_attempt_raw)
        except ValueError:
            next_attempt_at = None
    return RequirementTaskEventView(
        sequence_number=event.sequence_number,
        task_id=event.task_id,
        status=event.event_type,
        error_code=error_code_raw if isinstance(error_code_raw, str) else None,
        retryable=retryable_raw is True,
        next_attempt_at=next_attempt_at,
        created_at=event.created_at,
    )


def _draft_view(
    draft: JobRequirementDraft,
    *,
    schema: JobRequirementSchemaVersion,
    read_only_reason: str | None,
    pending_upgrade_items: list[dict[str, object]] | None = None,
) -> RequirementDraftView:
    return RequirementDraftView(
        id=draft.id,
        task_id=draft.task_id,
        input_snapshot_id=draft.input_snapshot_id,
        source_version_id=draft.source_version_id,
        requirement_schema_version_id=draft.requirement_schema_version_id,
        status=draft.status,
        revision=draft.revision,
        result=draft.result_json,
        updated_by=draft.updated_by,
        status_changed_at=draft.status_changed_at,
        read_only_reason=read_only_reason,
        field_catalog=draft_view_catalog(schema.field_catalog),
        chinese_identity_values=list(schema.chinese_identity_values),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        pending_upgrade_items=pending_upgrade_items or [],
    )


def draft_view_catalog(value: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(value))
