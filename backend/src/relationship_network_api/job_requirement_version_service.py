"""Confirm editable drafts into immutable per-job requirement versions."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast, final

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from relationship_network_api import job_requirement_draft_service as draft_service
from relationship_network_api import tenant_audit_service, tenant_context
from relationship_network_api.job_requirement_service import (
    RequirementDraftView,
    RequirementVersionView,
    draft_view_catalog,
)
from relationship_network_api.job_requirement_validation import (
    INVALID_SCHEMA,
    RequirementResultValidationError,
    confirmability_errors,
    validate_editable_requirement_document,
)
from relationship_network_api.job_service import JobNotFoundError
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    JOB_STATUS_ARCHIVED,
    Job,
    JobRequirementDraft,
    JobRequirementParsingTask,
    JobRequirementSchemaVersion,
    JobRequirementVersion,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DRAFT_NOT_FOUND: Final = draft_service.DRAFT_NOT_FOUND
DRAFT_REVISION_CONFLICT: Final = draft_service.DRAFT_REVISION_CONFLICT
DRAFT_LOCKED: Final = draft_service.DRAFT_LOCKED
DRAFT_NOT_EDITABLE: Final = draft_service.DRAFT_NOT_EDITABLE
DRAFT_INVALID: Final = draft_service.DRAFT_INVALID
JOB_ARCHIVED: Final = draft_service.JOB_ARCHIVED
VERSION_REQUIRED: Final = "requirement_version_required"
VERSION_NOT_FOUND: Final = "requirement_version_not_found"
EDITABLE_DRAFT_EXISTS: Final = "requirement_editable_draft_exists"
RESEARCH_TOPIC_EMPTY: Final = "research_topic_query_empty"
SOURCE_CONFLICTS_UNRESOLVED: Final = "source_conflicts_unresolved"

ACTION_CONFIRM: Final = "job_requirement_draft.confirm"
ACTION_COPY: Final = "job_requirement_version.copy"
TARGET_TYPE_DRAFT: Final = "job_requirement_draft"
TARGET_TYPE_VERSION: Final = "job_requirement_version"

NONTERMINAL_STATUSES: Final = draft_service.NONTERMINAL_STATUSES


@final
class RequirementVersionError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        latest: RequirementDraftView | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.latest = latest


@final
@dataclass(frozen=True)
class ConfirmRequirementView:
    version: RequirementVersionView
    draft: RequirementDraftView


async def confirm_draft(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_revision: int,
) -> ConfirmRequirementView:
    """Lock the job, allocate the next version number, and switch the current pointer."""
    job = await _locked_job(session, tenant_id=tenant_id, job_id=job_id)
    draft = await _locked_draft(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise RequirementVersionError(DRAFT_NOT_FOUND)
    schema = await _schema(session, draft.requirement_schema_version_id)
    await _assert_confirmable(
        session,
        job=job,
        draft=draft,
        schema=schema,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
    )
    blockers = confirmability_errors(draft.result_json)
    if blockers:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=blockers[0],
        )
    try:
        validated = validate_editable_requirement_document(
            draft.result_json,
            schema=manifest.read_requirement_editor_schema(draft.requirement_schema_version_id),
            asset=_asset(draft.requirement_schema_version_id),
        )
    except RequirementResultValidationError as error:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=DRAFT_INVALID,
        )
        message = "unreachable"
        raise AssertionError(message) from error

    next_number = await _next_version_number(session, tenant_id=tenant_id, job_id=job_id)
    confirmed_at = datetime.now(UTC)
    version = JobRequirementVersion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_id=job_id,
        version_number=next_number,
        requirement_schema_version_id=draft.requirement_schema_version_id,
        result_json=deepcopy(validated),
        draft_id=draft.id,
        input_snapshot_id=draft.input_snapshot_id,
        source_version_id=draft.source_version_id,
        confirmed_by=actor_user_id,
        confirmed_at=confirmed_at,
    )
    session.add(version)
    await session.flush()
    job.current_requirement_version_id = version.id
    if job.legacy_requirement_exempt:
        job.legacy_requirement_exempt = False
    job.updated_at = confirmed_at
    draft.status = "confirmed"
    draft.revision += 1
    draft.updated_by = actor_user_id
    draft.status_changed_at = confirmed_at
    draft.result_json = validated
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_CONFIRM,
        target_type=TARGET_TYPE_DRAFT,
        target_id=str(draft.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"version={version.version_number}",
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft_id),
            action=ACTION_CONFIRM,
            code=DRAFT_REVISION_CONFLICT,
        )
        message = "unreachable"
        raise AssertionError(message) from error
    return ConfirmRequirementView(
        version=RequirementVersionView(
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
        ),
        draft=_draft_view(draft, schema=schema, read_only_reason=draft_service.READ_ONLY_STATUS),
    )


async def copy_current_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> RequirementDraftView:
    """Copy the current immutable version into a new editable draft without an LLM call."""
    job = await _locked_job(session, tenant_id=tenant_id, job_id=job_id)
    if job.status == JOB_STATUS_ARCHIVED:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_VERSION,
            target_id=str(job_id),
            action=ACTION_COPY,
            code=JOB_ARCHIVED,
        )
    if job.current_requirement_version_id is None:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_VERSION,
            target_id=str(job_id),
            action=ACTION_COPY,
            code=VERSION_NOT_FOUND,
        )
    version = (
        await session.execute(
            select(JobRequirementVersion)
            .where(
                JobRequirementVersion.id == job.current_requirement_version_id,
                JobRequirementVersion.tenant_id == tenant_id,
                JobRequirementVersion.job_id == job_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    existing = (
        await session.execute(
            select(JobRequirementDraft.id).where(
                JobRequirementDraft.tenant_id == tenant_id,
                JobRequirementDraft.job_id == job_id,
                JobRequirementDraft.status == "editable",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_VERSION,
            target_id=str(version.id),
            action=ACTION_COPY,
            code=EDITABLE_DRAFT_EXISTS,
        )
    schema = await _schema(session, version.requirement_schema_version_id)
    now = datetime.now(UTC)
    draft = JobRequirementDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_id=job_id,
        task_id=None,
        input_snapshot_id=version.input_snapshot_id,
        source_version_id=version.id,
        requirement_schema_version_id=version.requirement_schema_version_id,
        status="editable",
        revision=1,
        result_json=deepcopy(version.result_json),
        created_by=actor_user_id,
        updated_by=actor_user_id,
        status_changed_at=now,
    )
    session.add(draft)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_COPY,
        target_type=TARGET_TYPE_VERSION,
        target_id=str(version.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"draft={draft.id}",
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_VERSION,
            target_id=str(version.id),
            action=ACTION_COPY,
            code=EDITABLE_DRAFT_EXISTS,
        )
        message = "unreachable"
        raise AssertionError(message) from error
    return _draft_view(draft, schema=schema, read_only_reason=None)


async def list_versions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[uuid.UUID | None, list[RequirementVersionView]]:
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
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
    return current_id, [
        RequirementVersionView(
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
            is_current=version.id == current_id,
        )
        for version in versions
    ]


async def _assert_confirmable(  # noqa: PLR0913
    session: AsyncSession,
    *,
    job: Job,
    draft: JobRequirementDraft,
    schema: JobRequirementSchemaVersion,
    expected_revision: int,
    actor_user_id: uuid.UUID,
) -> None:
    reason = await draft_service.read_only_reason(session, job=job, draft=draft)
    if reason == draft_service.READ_ONLY_JOB_ARCHIVED:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=JOB_ARCHIVED,
        )
    if reason == draft_service.READ_ONLY_REPLACEMENT:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=DRAFT_LOCKED,
        )
    if reason == draft_service.READ_ONLY_STATUS:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=DRAFT_NOT_EDITABLE,
        )
    if draft.revision != expected_revision:
        latest = _draft_view(draft, schema=schema, read_only_reason=reason)
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=DRAFT_REVISION_CONFLICT,
            latest=latest,
        )
    replacement = (
        await session.execute(
            select(JobRequirementParsingTask.id).where(
                JobRequirementParsingTask.tenant_id == draft.tenant_id,
                JobRequirementParsingTask.job_id == draft.job_id,
                JobRequirementParsingTask.replaces_draft_id == draft.id,
                JobRequirementParsingTask.status.in_(NONTERMINAL_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if replacement is not None:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            target_type=TARGET_TYPE_DRAFT,
            target_id=str(draft.id),
            action=ACTION_CONFIRM,
            code=DRAFT_LOCKED,
        )


async def _next_version_number(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> int:
    maximum = (
        await session.execute(
            select(func.coalesce(func.max(JobRequirementVersion.version_number), 0)).where(
                JobRequirementVersion.tenant_id == tenant_id,
                JobRequirementVersion.job_id == job_id,
            )
        )
    ).scalar_one()
    return cast("int", maximum) + 1


async def _reject(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_type: str,
    target_id: str,
    action: str,
    code: str,
    latest: RequirementDraftView | None = None,
) -> None:
    await session.rollback()
    await tenant_context.set_tenant_context(session, tenant_id)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=tenant_audit_service.AUDIT_RESULT_FAILURE,
        detail=code,
    )
    await session.commit()
    raise RequirementVersionError(code, latest=latest)


async def _locked_job(session: AsyncSession, *, tenant_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = (
        await session.execute(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError
    return job


async def _load_job(session: AsyncSession, *, tenant_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = (
        await session.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError
    return job


async def _locked_draft(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> JobRequirementDraft | None:
    return (
        await session.execute(
            select(JobRequirementDraft)
            .where(
                JobRequirementDraft.id == draft_id,
                JobRequirementDraft.tenant_id == tenant_id,
                JobRequirementDraft.job_id == job_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _schema(session: AsyncSession, schema_id: str) -> JobRequirementSchemaVersion:
    return (
        await session.execute(
            select(JobRequirementSchemaVersion).where(JobRequirementSchemaVersion.id == schema_id)
        )
    ).scalar_one()


def _asset(schema_id: str) -> manifest.RequirementSchemaAsset:
    asset = next(
        (item for item in manifest.REQUIREMENT_SCHEMA_ASSETS if item.id == schema_id),
        None,
    )
    if asset is None or asset.editor_path is None:
        message = "editor Schema is unavailable"
        raise RequirementResultValidationError(INVALID_SCHEMA, message)
    return asset


def _draft_view(
    draft: JobRequirementDraft,
    *,
    schema: JobRequirementSchemaVersion,
    read_only_reason: str | None,
) -> RequirementDraftView:
    return RequirementDraftView(
        id=draft.id,
        task_id=draft.task_id,
        input_snapshot_id=draft.input_snapshot_id,
        source_version_id=draft.source_version_id,
        requirement_schema_version_id=draft.requirement_schema_version_id,
        status=draft.status,
        revision=draft.revision,
        result=deepcopy(draft.result_json),
        updated_by=draft.updated_by,
        status_changed_at=draft.status_changed_at,
        read_only_reason=read_only_reason,
        field_catalog=draft_view_catalog(schema.field_catalog),
        chinese_identity_values=list(schema.chinese_identity_values),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )
