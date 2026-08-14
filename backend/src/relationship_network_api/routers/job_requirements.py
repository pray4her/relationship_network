"""Tenant HTTP boundary for preparing and viewing generated job requirement drafts."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, ClassVar, cast, final

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import job_requirement_draft_service as draft_service
from relationship_network_api import job_requirement_history_service as history_service
from relationship_network_api import job_requirement_service as service
from relationship_network_api import job_requirement_version_service as version_service
from relationship_network_api import tenant_audit_service, usage_service
from relationship_network_api.config import load_database_settings
from relationship_network_api.deps import (
    PERMISSION_DENIED_DETAIL,
    SUBSCRIPTION_READ_ONLY_DETAIL,
    TenantContext,
    get_db_session,
    get_tenant_context,
    require_permission,
)
from relationship_network_api.durable_task import (
    HEARTBEAT_SECONDS,
    MAX_CONNECTION_SECONDS,
    POLL_SECONDS,
    SSE_RESPONSE_HEADERS,
    encode_sse_event,
    encode_sse_heartbeat,
    parse_last_event_id,
)
from relationship_network_api.job_service import JOB_NOT_FOUND_DETAIL, JobNotFoundError

router = APIRouter()

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
require_requirement_jobs_read = require_permission("jobs:read")
JobsReadDep = Annotated[TenantContext, Depends(require_requirement_jobs_read)]
TASK_EVENT_CHANNEL = "job_requirement_parsing_task_events"
AUDIT_ACTION_WRITE_DENIED = "job_requirement.write_denied"
AUDIT_TARGET_JOB = "job"


async def require_requirement_jobs_manage_audited(
    job_id: uuid.UUID,
    session: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    """Require jobs:manage on a writable tenant, auditing authenticated denials.

    Only denials for an authenticated member inside their own tenant are
    recorded; anonymous requests and cross-tenant probes hidden by RLS never
    produce audit entries that could leak target existence.
    """
    detail: str | None = None
    if "jobs:manage" not in context.permissions:
        detail = PERMISSION_DENIED_DETAIL
    elif not await usage_service.is_tenant_writable(
        session,
        tenant_id=context.membership.tenant_id,
    ):
        detail = SUBSCRIPTION_READ_ONLY_DETAIL
    if detail is not None:
        tenant_audit_service.record_event(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            action=AUDIT_ACTION_WRITE_DENIED,
            target_type=AUDIT_TARGET_JOB,
            target_id=str(job_id),
            result=tenant_audit_service.AUDIT_RESULT_FAILURE,
            detail=detail,
        )
        await session.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return context


JobsManageDep = Annotated[
    TenantContext,
    Depends(require_requirement_jobs_manage_audited),
]


@final
@dataclass(frozen=True)
class _TaskEventListener:
    connection: asyncpg.Connection
    wakeup: asyncio.Event
    callback: Callable[[asyncpg.Connection, int, str, str], None]

    async def close(self) -> None:
        with contextlib.suppress(asyncpg.PostgresError, OSError, TimeoutError):
            await self.connection.remove_listener(TASK_EVENT_CHANNEL, self.callback)
        with contextlib.suppress(asyncpg.PostgresError, OSError, TimeoutError):
            await self.connection.close(timeout=1.0)


async def _try_listen_for_task_events(task_id: uuid.UUID) -> _TaskEventListener | None:
    """Best-effort wakeups; persisted event reads remain the correctness boundary."""
    dsn = str(load_database_settings().database_url).replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )
    try:
        connection = cast("asyncpg.Connection", await asyncpg.connect(dsn=dsn, timeout=1))
    except (asyncpg.PostgresError, OSError, TimeoutError, ValueError):
        return None
    wakeup = asyncio.Event()
    task_prefix = f"{task_id}:"

    def notify(
        _connection: asyncpg.Connection,
        _process_id: int,
        _channel: str,
        payload: str,
    ) -> None:
        if payload.startswith(task_prefix):
            wakeup.set()

    try:
        await connection.add_listener(TASK_EVENT_CHANNEL, notify)
    except (asyncpg.PostgresError, OSError):
        with contextlib.suppress(asyncpg.PostgresError, OSError, TimeoutError):
            await connection.close(timeout=1.0)
        return None
    return _TaskEventListener(connection=connection, wakeup=wakeup, callback=notify)


class RequirementSourceSubmissionRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    corrected_text: str

    @field_validator("source_id")
    @classmethod
    def source_id_must_not_have_surrounding_whitespace(cls, value: str) -> str:
        if value != value.strip():
            message = "source_id must not contain surrounding whitespace"
            raise ValueError(message)
        return value


class CreateRequirementTaskRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=128)
    sources: list[RequirementSourceSubmissionRequest] = Field(max_length=101)

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_must_not_have_surrounding_whitespace(cls, value: str) -> str:
        if value != value.strip():
            message = "idempotency_key must not contain surrounding whitespace"
            raise ValueError(message)
        return value


class RequirementSourceResponse(BaseModel):
    source_id: str
    source_kind: str
    material_id: uuid.UUID | None
    label: str
    original_text: str
    scan_status: str
    created_at: datetime | None


class RequirementTaskResponse(BaseModel):
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


class RequirementTaskEventResponse(BaseModel):
    sequence_number: int
    task_id: uuid.UUID
    status: str
    error_code: str | None
    retryable: bool
    next_attempt_at: datetime | None
    created_at: datetime


class RequirementDraftResponse(BaseModel):
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
    pending_upgrade_items: list[dict[str, object]]


class SchemaUpgradeRecordResponse(BaseModel):
    id: uuid.UUID
    draft_id: uuid.UUID
    from_schema_version_id: str
    to_schema_version_id: str
    converter_version: str
    item_mappings: list[dict[str, object]]
    lossy_resolutions: list[dict[str, object]]
    actor_user_id: uuid.UUID | None
    created_at: datetime


class SchemaUpgradeResponse(BaseModel):
    draft: RequirementDraftResponse
    upgrade: SchemaUpgradeRecordResponse


class RequirementVersionSummaryResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    requirement_schema_version_id: str
    draft_id: uuid.UUID
    source_version_id: uuid.UUID | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime
    created_at: datetime
    is_current: bool


class RequirementVersionResponse(BaseModel):
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


class RequirementWorkspaceResponse(BaseModel):
    configuration_ready: bool
    input_character_limit: int
    sources: list[RequirementSourceResponse]
    task: RequirementTaskResponse | None
    draft: RequirementDraftResponse | None
    current_version: RequirementVersionResponse | None
    versions: list[RequirementVersionSummaryResponse]
    legacy_requirement_exempt: bool
    matching_blocked: bool


class RequirementHistoryDraftResponse(BaseModel):
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


class RequirementHistorySourceResponse(BaseModel):
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


class RequirementHistoryEventResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    result: str
    detail: str
    created_at: datetime


class RequirementHistoryResponse(BaseModel):
    tasks: list[RequirementTaskResponse]
    drafts: list[RequirementHistoryDraftResponse]
    versions: list[RequirementVersionSummaryResponse]
    schema_upgrades: list[SchemaUpgradeRecordResponse]
    sources: list[RequirementHistorySourceResponse]
    change_events: list[RequirementHistoryEventResponse]


class ConfirmRequirementResponse(BaseModel):
    version: RequirementVersionResponse
    draft: RequirementDraftResponse


class RequirementConditionSubmissionRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    item_id: uuid.UUID | None = None
    field: str = Field(max_length=100)
    operator: str = Field(max_length=50)
    value: object
    description: str = Field(max_length=2000)


class RequirementUnsupportedSubmissionRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    item_id: uuid.UUID | None = None
    description: str = Field(max_length=2000)


class RequirementConflictSubmissionRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    resolution_note: str | None = Field(default=None, max_length=2000)


class RequirementDraftSubmissionRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    hard_conditions: list[RequirementConditionSubmissionRequest] = Field(max_length=100)
    preference_conditions: list[RequirementConditionSubmissionRequest] = Field(max_length=100)
    research_topic_query: str = Field(max_length=4000)
    unsupported_conditions: list[RequirementUnsupportedSubmissionRequest] = Field(max_length=100)
    source_conflicts: list[RequirementConflictSubmissionRequest] = Field(max_length=50)


class UpdateRequirementDraftRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    result: RequirementDraftSubmissionRequest


class AbandonRequirementDraftRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class ConfirmRequirementDraftRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class UpgradeRequirementDraftSchemaRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class LossyResolutionRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    resolution: str = Field(max_length=30)

    @field_validator("resolution")
    @classmethod
    def resolution_must_be_supported(cls, value: str) -> str:
        if value not in {draft_service.RESOLUTION_DROP, draft_service.RESOLUTION_DOWNGRADE}:
            message = "resolution must be drop or downgrade_unsupported"
            raise ValueError(message)
        return value


class ResolveSchemaUpgradeLossyRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    resolutions: list[LossyResolutionRequest] = Field(min_length=1, max_length=100)


def _task_response(view: service.RequirementTaskView) -> RequirementTaskResponse:
    return RequirementTaskResponse(**view.__dict__)


def _draft_response(
    view: service.RequirementDraftView | draft_service.RequirementDraftMutationView,
) -> RequirementDraftResponse:
    return RequirementDraftResponse(**vars(view))


def _version_response(view: service.RequirementVersionView) -> RequirementVersionResponse:
    return RequirementVersionResponse(**view.__dict__)


def _version_summary_response(
    view: service.RequirementVersionSummaryView,
) -> RequirementVersionSummaryResponse:
    return RequirementVersionSummaryResponse(**view.__dict__)


@router.get("/jobs/{job_id}/requirement-generation")
async def read_requirement_generation(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> RequirementWorkspaceResponse:
    try:
        workspace = await service.load_workspace(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=JOB_NOT_FOUND_DETAIL
        ) from error
    return RequirementWorkspaceResponse(
        configuration_ready=workspace.configuration_ready,
        input_character_limit=workspace.input_character_limit,
        sources=[RequirementSourceResponse(**source.__dict__) for source in workspace.sources],
        task=None if workspace.task is None else _task_response(workspace.task),
        draft=None if workspace.draft is None else _draft_response(workspace.draft),
        current_version=(
            None
            if workspace.current_version is None
            else _version_response(workspace.current_version)
        ),
        versions=[_version_summary_response(item) for item in workspace.versions],
        legacy_requirement_exempt=workspace.legacy_requirement_exempt,
        matching_blocked=workspace.matching_blocked,
    )


@router.post(
    "/jobs/{job_id}/requirement-parsing-tasks",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_requirement_parsing_task(
    job_id: uuid.UUID,
    body: CreateRequirementTaskRequest,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementTaskResponse:
    try:
        task = await service.create_parsing_task(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            actor_user_id=context.authentication.user.id,
            idempotency_key=body.idempotency_key,
            submissions=[
                service.RequirementSourceSubmission(
                    source_id=source.source_id,
                    corrected_text=source.corrected_text,
                )
                for source in body.sources
            ],
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=JOB_NOT_FOUND_DETAIL
        ) from error
    except service.RequirementGenerationError as error:
        status_code = _error_status(error.code)
        raise HTTPException(status_code=status_code, detail=error.code) from error
    return _task_response(task)


@router.post("/jobs/{job_id}/requirement-parsing-tasks/{task_id}/cancel")
async def cancel_requirement_parsing_task(
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementTaskResponse:
    try:
        task = await service.cancel_parsing_task(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            task_id=task_id,
            actor_user_id=context.authentication.user.id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except service.RequirementGenerationError as error:
        raise HTTPException(status_code=_error_status(error.code), detail=error.code) from error
    return _task_response(task)


@router.put("/jobs/{job_id}/requirement-drafts/{draft_id}", response_model=None)
async def update_requirement_draft(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    body: UpdateRequirementDraftRequest,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementDraftResponse | JSONResponse:
    try:
        draft = await draft_service.update_requirement_draft(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            draft_id=draft_id,
            actor_user_id=context.authentication.user.id,
            expected_revision=body.expected_revision,
            submitted=body.result.model_dump(mode="python"),
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except draft_service.RequirementDraftError as error:
        if error.code == draft_service.DRAFT_REVISION_CONFLICT and error.latest is not None:
            latest = _draft_response(error.latest).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": error.code, "draft": latest},
            )
        raise HTTPException(
            status_code=_draft_error_status(error.code),
            detail=error.code,
        ) from error
    return _draft_response(draft)


@router.post(
    "/jobs/{job_id}/requirement-drafts/{draft_id}/abandon",
    response_model=None,
)
async def abandon_requirement_draft(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    body: AbandonRequirementDraftRequest,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementDraftResponse | JSONResponse:
    try:
        draft = await draft_service.abandon_requirement_draft(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            draft_id=draft_id,
            actor_user_id=context.authentication.user.id,
            expected_revision=body.expected_revision,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except draft_service.RequirementDraftError as error:
        if error.code == draft_service.DRAFT_REVISION_CONFLICT and error.latest is not None:
            latest = _draft_response(error.latest).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": error.code, "draft": latest},
            )
        raise HTTPException(
            status_code=_draft_error_status(error.code),
            detail=error.code,
        ) from error
    return _draft_response(draft)


@router.post(
    "/jobs/{job_id}/requirement-drafts/{draft_id}/confirm",
    response_model=None,
)
async def confirm_requirement_draft(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    body: ConfirmRequirementDraftRequest,
    context: JobsManageDep,
    session: DbSession,
) -> ConfirmRequirementResponse | JSONResponse:
    try:
        confirmed = await version_service.confirm_draft(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            draft_id=draft_id,
            actor_user_id=context.authentication.user.id,
            expected_revision=body.expected_revision,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except version_service.RequirementVersionError as error:
        if error.code == version_service.DRAFT_REVISION_CONFLICT and error.latest is not None:
            latest = _draft_response(error.latest).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": error.code, "draft": latest},
            )
        raise HTTPException(
            status_code=_version_error_status(error.code),
            detail=error.code,
        ) from error
    return ConfirmRequirementResponse(
        version=_version_response(confirmed.version),
        draft=_draft_response(confirmed.draft),
    )


@router.post(
    "/jobs/{job_id}/requirement-drafts/{draft_id}/schema-upgrade",
    response_model=None,
)
async def upgrade_requirement_draft_schema(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    body: UpgradeRequirementDraftSchemaRequest,
    context: JobsManageDep,
    session: DbSession,
) -> SchemaUpgradeResponse | JSONResponse:
    try:
        result = await draft_service.upgrade_draft_schema(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            draft_id=draft_id,
            actor_user_id=context.authentication.user.id,
            expected_revision=body.expected_revision,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except draft_service.RequirementDraftError as error:
        if error.code == draft_service.DRAFT_REVISION_CONFLICT and error.latest is not None:
            latest = _draft_response(error.latest).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": error.code, "draft": latest},
            )
        raise HTTPException(
            status_code=_draft_error_status(error.code),
            detail=error.code,
        ) from error
    return SchemaUpgradeResponse(
        draft=_draft_response(result.draft),
        upgrade=SchemaUpgradeRecordResponse(**vars(result.upgrade)),
    )


@router.post(
    "/jobs/{job_id}/requirement-drafts/{draft_id}/schema-upgrades/{upgrade_id}/resolve",
    response_model=None,
)
async def resolve_requirement_schema_upgrade_lossy(  # noqa: PLR0913
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    upgrade_id: uuid.UUID,
    body: ResolveSchemaUpgradeLossyRequest,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementDraftResponse | JSONResponse:
    try:
        draft = await draft_service.resolve_schema_upgrade_lossy_items(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            draft_id=draft_id,
            upgrade_id=upgrade_id,
            actor_user_id=context.authentication.user.id,
            expected_revision=body.expected_revision,
            resolutions=[
                draft_service.LossyResolutionSubmission(
                    item_id=str(item.item_id),
                    resolution=item.resolution,
                )
                for item in body.resolutions
            ],
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except draft_service.RequirementDraftError as error:
        if error.code == draft_service.DRAFT_REVISION_CONFLICT and error.latest is not None:
            latest = _draft_response(error.latest).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": error.code, "draft": latest},
            )
        raise HTTPException(
            status_code=_draft_error_status(error.code),
            detail=error.code,
        ) from error
    return _draft_response(draft)


@router.post("/jobs/{job_id}/requirement-versions/copy-current", response_model=None)
async def copy_current_requirement_version(
    job_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
) -> RequirementDraftResponse | JSONResponse:
    try:
        draft = await version_service.copy_current_version(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            actor_user_id=context.authentication.user.id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except version_service.RequirementVersionError as error:
        raise HTTPException(
            status_code=_version_error_status(error.code),
            detail=error.code,
        ) from error
    return _draft_response(draft)


@router.get("/jobs/{job_id}/requirement-versions")
async def list_requirement_versions(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> list[RequirementVersionResponse]:
    try:
        _, versions = await version_service.list_versions(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    return [_version_response(item) for item in versions]


@router.get("/jobs/{job_id}/requirement-history")
async def read_requirement_history(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> RequirementHistoryResponse:
    try:
        history = await history_service.load_requirement_history(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    return RequirementHistoryResponse(
        tasks=[_task_response(item) for item in history.tasks],
        drafts=[RequirementHistoryDraftResponse(**vars(item)) for item in history.drafts],
        versions=[_version_summary_response(item) for item in history.versions],
        schema_upgrades=[
            SchemaUpgradeRecordResponse(**vars(item)) for item in history.schema_upgrades
        ],
        sources=[RequirementHistorySourceResponse(**vars(item)) for item in history.sources],
        change_events=[
            RequirementHistoryEventResponse(
                id=item.id,
                actor_user_id=item.actor_user_id,
                action=item.action,
                target_type=item.target_type,
                target_id=item.target_id,
                result=item.result,
                detail=item.detail,
                created_at=item.created_at,
            )
            for item in history.change_events
        ],
    )


@router.get("/jobs/{job_id}/requirement-parsing-tasks/{task_id}/events")
async def stream_requirement_parsing_task_events(  # noqa: C901, PLR0913
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    request: Request,
    context: JobsReadDep,
    session: DbSession,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        after_sequence = parse_last_event_id(last_event_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=service.INVALID_LAST_EVENT_ID,
        ) from error
    try:
        _ = await service.get_task(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            task_id=task_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except service.RequirementGenerationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.code) from error

    async def event_stream() -> AsyncIterator[str]:
        started_at = time.monotonic()
        last_heartbeat_at = started_at
        cursor = after_sequence
        listener: _TaskEventListener | None = None
        listener_attempted = False
        try:
            while time.monotonic() - started_at < MAX_CONNECTION_SECONDS:
                if await request.is_disconnected():
                    return
                events = await service.list_task_events(
                    session,
                    tenant_id=context.tenant_id,
                    job_id=job_id,
                    task_id=task_id,
                    after_sequence=cursor,
                )
                for event in events:
                    cursor = event.sequence_number
                    data = RequirementTaskEventResponse(**event.__dict__).model_dump(mode="json")
                    yield encode_sse_event(
                        sequence_number=event.sequence_number,
                        event_type=event.status,
                        data=data,
                    )
                    if event.status in {"succeeded", "failed", "cancelled"}:
                        return
                now = time.monotonic()
                if now - last_heartbeat_at >= HEARTBEAT_SECONDS:
                    yield encode_sse_heartbeat()
                    last_heartbeat_at = now
                if not listener_attempted:
                    listener = await _try_listen_for_task_events(task_id)
                    listener_attempted = True
                if listener is None:
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                listener.wakeup.clear()
                with contextlib.suppress(TimeoutError):
                    _ = await asyncio.wait_for(listener.wakeup.wait(), timeout=POLL_SECONDS)
        finally:
            if listener is not None:
                await listener.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )


def _error_status(code: str) -> int:
    if code == service.SOURCE_NOT_FOUND:
        return status.HTTP_404_NOT_FOUND
    if code == service.TASK_NOT_FOUND:
        return status.HTTP_404_NOT_FOUND
    if code == service.INPUT_TOO_LARGE:
        return status.HTTP_413_CONTENT_TOO_LARGE
    if code in {
        service.EMPTY_INPUT,
        service.EMPTY_MATERIAL_CORRECTION,
    }:
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    if code == service.CREATION_RATE_LIMITED:
        return status.HTTP_429_TOO_MANY_REQUESTS
    return status.HTTP_409_CONFLICT


def _draft_error_status(code: str) -> int:
    if code in {
        draft_service.DRAFT_NOT_FOUND,
        draft_service.SCHEMA_UPGRADE_NOT_FOUND,
    }:
        return status.HTTP_404_NOT_FOUND
    if code in {
        draft_service.DRAFT_INVALID,
        draft_service.SCHEMA_UPGRADE_RESOLUTION_INVALID,
    }:
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_409_CONFLICT


def _version_error_status(code: str) -> int:
    if code in {
        version_service.DRAFT_NOT_FOUND,
        version_service.VERSION_NOT_FOUND,
    }:
        return status.HTTP_404_NOT_FOUND
    if code == version_service.DRAFT_INVALID:
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_409_CONFLICT
