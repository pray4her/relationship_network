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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import job_requirement_service as service
from relationship_network_api.config import load_database_settings
from relationship_network_api.deps import (
    TenantContext,
    get_db_session,
    require_permission,
    require_writable_permission,
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
require_requirement_jobs_manage = require_writable_permission("jobs:manage")
JobsReadDep = Annotated[TenantContext, Depends(require_requirement_jobs_read)]
JobsManageDep = Annotated[
    TenantContext,
    Depends(require_requirement_jobs_manage),
]
TASK_EVENT_CHANNEL = "job_requirement_parsing_task_events"


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
    task_id: uuid.UUID
    input_snapshot_id: uuid.UUID
    requirement_schema_version_id: str
    status: str
    revision: int
    result: dict[str, object]
    created_at: datetime
    updated_at: datetime


class RequirementWorkspaceResponse(BaseModel):
    configuration_ready: bool
    input_character_limit: int
    sources: list[RequirementSourceResponse]
    task: RequirementTaskResponse | None
    draft: RequirementDraftResponse | None


def _task_response(view: service.RequirementTaskView) -> RequirementTaskResponse:
    return RequirementTaskResponse(**view.__dict__)


def _draft_response(view: service.RequirementDraftView) -> RequirementDraftResponse:
    return RequirementDraftResponse(**view.__dict__)


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
