"""Tenant-facing long-term history view for the job requirement pipeline.

Members with jobs:read can inspect parsing tasks, drafts, versions, schema
upgrade records, source metadata, and recorded change facts for one job. The
view deliberately exposes business-layer facts only: no platform cost, no
provider diagnostics, and no raw LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from sqlalchemy import and_, or_, select

from relationship_network_api import job_requirement_draft_service as draft_service
from relationship_network_api import job_requirement_service as service
from relationship_network_api.job_service import JobNotFoundError
from relationship_network_api.models import (
    Job,
    JobRequirementDraft,
    JobRequirementDraftSchemaUpgrade,
    JobRequirementInputSource,
    JobRequirementParsingTask,
    JobRequirementVersion,
    TenantAuditEvent,
)
from relationship_network_api.tenant_audit_service import TenantAuditEventView

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

HISTORY_LIST_LIMIT: Final = 200
AUDIT_ACTION_PREFIX: Final = "job_requirement%"
AUDIT_ACTION_WRITE_DENIED: Final = "job_requirement.write_denied"
TARGET_TYPE_JOB: Final = "job"


@final
@dataclass(frozen=True)
class RequirementHistoryDraftView:
    """Business-layer summary of a long-retained terminal or editable draft."""

    id: uuid.UUID
    task_id: uuid.UUID | None
    input_snapshot_id: uuid.UUID | None
    source_version_id: uuid.UUID | None
    requirement_schema_version_id: str
    status: str
    revision: int
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    status_changed_at: datetime
    created_at: datetime
    updated_at: datetime


@final
@dataclass(frozen=True)
class RequirementHistorySourceView:
    """Source metadata; bodies stay in the generation workspace, never here."""

    snapshot_id: uuid.UUID
    source_id: str
    source_kind: str
    material_id: uuid.UUID | None
    position: int
    original_sha256: str
    sent_sha256: str
    unicode_characters: int
    edited_by: uuid.UUID | None
    edited_at: datetime
    body_purged_at: datetime | None


@final
@dataclass(frozen=True)
class RequirementHistoryView:
    tasks: list[service.RequirementTaskView]
    drafts: list[RequirementHistoryDraftView]
    versions: list[service.RequirementVersionSummaryView]
    schema_upgrades: list[draft_service.SchemaUpgradeRecordView]
    sources: list[RequirementHistorySourceView]
    change_events: list[TenantAuditEventView]


async def load_requirement_history(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> RequirementHistoryView:
    """Assemble the per-job long-term history grouped by business layer."""
    job = (
        await session.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError

    tasks = list(
        (
            await session.execute(
                select(JobRequirementParsingTask)
                .where(
                    JobRequirementParsingTask.tenant_id == tenant_id,
                    JobRequirementParsingTask.job_id == job_id,
                )
                .order_by(JobRequirementParsingTask.created_at.desc())
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    drafts = list(
        (
            await session.execute(
                select(JobRequirementDraft)
                .where(
                    JobRequirementDraft.tenant_id == tenant_id,
                    JobRequirementDraft.job_id == job_id,
                )
                .order_by(JobRequirementDraft.created_at.desc())
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    versions = list(
        (
            await session.execute(
                select(JobRequirementVersion)
                .where(
                    JobRequirementVersion.tenant_id == tenant_id,
                    JobRequirementVersion.job_id == job_id,
                )
                .order_by(JobRequirementVersion.version_number.desc())
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    upgrades = list(
        (
            await session.execute(
                select(JobRequirementDraftSchemaUpgrade)
                .where(
                    JobRequirementDraftSchemaUpgrade.tenant_id == tenant_id,
                    JobRequirementDraftSchemaUpgrade.job_id == job_id,
                )
                .order_by(JobRequirementDraftSchemaUpgrade.created_at.desc())
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    sources = list(
        (
            await session.execute(
                select(JobRequirementInputSource)
                .where(
                    JobRequirementInputSource.tenant_id == tenant_id,
                    JobRequirementInputSource.job_id == job_id,
                )
                .order_by(
                    JobRequirementInputSource.snapshot_id,
                    JobRequirementInputSource.position,
                )
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    target_ids = {str(item.id) for item in (*tasks, *drafts, *versions)}
    event_filters = [
        and_(
            TenantAuditEvent.target_type == TARGET_TYPE_JOB,
            TenantAuditEvent.target_id == str(job_id),
            TenantAuditEvent.action == AUDIT_ACTION_WRITE_DENIED,
        ),
    ]
    if target_ids:
        event_filters.append(
            and_(
                TenantAuditEvent.target_id.in_(target_ids),
                TenantAuditEvent.action.like(AUDIT_ACTION_PREFIX),
            )
        )
    change_events = (
        (
            await session.execute(
                select(TenantAuditEvent)
                .where(
                    TenantAuditEvent.tenant_id == tenant_id,
                    or_(*event_filters),
                )
                .order_by(TenantAuditEvent.created_at.desc())
                .limit(HISTORY_LIST_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    current_id = job.current_requirement_version_id
    return RequirementHistoryView(
        tasks=[_task_view(task) for task in tasks],
        drafts=[_draft_view(draft) for draft in drafts],
        versions=[
            service.RequirementVersionSummaryView(
                id=version.id,
                version_number=version.version_number,
                requirement_schema_version_id=version.requirement_schema_version_id,
                draft_id=version.draft_id,
                source_version_id=version.source_version_id,
                confirmed_by=version.confirmed_by,
                confirmed_at=version.confirmed_at,
                created_at=version.created_at,
                is_current=version.id == current_id,
            )
            for version in versions
        ],
        schema_upgrades=[_upgrade_view(upgrade) for upgrade in upgrades],
        sources=[_source_view(source) for source in sources],
        change_events=[_audit_view(event) for event in change_events],
    )


def _task_view(task: JobRequirementParsingTask) -> service.RequirementTaskView:
    return service.RequirementTaskView(
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


def _upgrade_view(
    upgrade: JobRequirementDraftSchemaUpgrade,
) -> draft_service.SchemaUpgradeRecordView:
    return draft_service.SchemaUpgradeRecordView(
        id=upgrade.id,
        draft_id=upgrade.draft_id,
        from_schema_version_id=upgrade.from_schema_version_id,
        to_schema_version_id=upgrade.to_schema_version_id,
        converter_version=upgrade.converter_version,
        item_mappings=upgrade.item_mappings,
        lossy_resolutions=upgrade.lossy_resolutions,
        actor_user_id=upgrade.actor_user_id,
        created_at=upgrade.created_at,
    )


def _audit_view(event: TenantAuditEvent) -> TenantAuditEventView:
    return TenantAuditEventView(
        id=event.id,
        tenant_id=event.tenant_id,
        actor_user_id=event.actor_user_id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        result=event.result,
        detail=event.detail,
        created_at=event.created_at,
    )


def _draft_view(draft: JobRequirementDraft) -> RequirementHistoryDraftView:
    return RequirementHistoryDraftView(
        id=draft.id,
        task_id=draft.task_id,
        input_snapshot_id=draft.input_snapshot_id,
        source_version_id=draft.source_version_id,
        requirement_schema_version_id=draft.requirement_schema_version_id,
        status=draft.status,
        revision=draft.revision,
        created_by=draft.created_by,
        updated_by=draft.updated_by,
        status_changed_at=draft.status_changed_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _source_view(source: JobRequirementInputSource) -> RequirementHistorySourceView:
    return RequirementHistorySourceView(
        snapshot_id=source.snapshot_id,
        source_id=source.source_id,
        source_kind=source.source_kind,
        material_id=source.material_id,
        position=source.position,
        original_sha256=source.original_sha256,
        sent_sha256=source.sent_sha256,
        unicode_characters=source.unicode_characters,
        edited_by=source.edited_by,
        edited_at=source.edited_at,
        body_purged_at=source.body_purged_at,
    )
