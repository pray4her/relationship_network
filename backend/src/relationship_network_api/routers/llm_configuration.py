import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, ClassVar, Final, final

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import llm_configuration_service as service
from relationship_network_api.auth_service import Authentication
from relationship_network_api.deps import get_db_session, require_platform_admin
from relationship_network_api.durable_task import (
    HEARTBEAT_SECONDS,
    MAX_CONNECTION_SECONDS,
    POLL_SECONDS,
    SSE_RESPONSE_HEADERS,
    encode_sse_event,
    encode_sse_heartbeat,
    parse_last_event_id,
)
from relationship_network_api.llm_assets.manifest import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
)
from relationship_network_api.openrouter import (
    DEFAULT_PARSING_TIMEOUT_SECONDS,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    MAX_PARSING_TIMEOUT_SECONDS,
    MAX_SEARCH_TIMEOUT_SECONDS,
    MIN_PARSING_TIMEOUT_SECONDS,
    MIN_SEARCH_TIMEOUT_SECONDS,
    CallTypeBinding,
    CandidateConfiguration,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
PlatformAdminDep = Annotated[Authentication, Depends(require_platform_admin)]

_TERMINAL_EVENTS: Final = frozenset({"succeeded", "failed", "conflicted", "cancelled"})


class CallBindingRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    prompt_version_id: str = Field(min_length=1, max_length=100)
    request_timeout_seconds: int

    @field_validator("prompt_version_id")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            message = "must not be blank"
            raise ValueError(message)
        return normalized


class ParsingCallBindingRequest(CallBindingRequest):
    request_timeout_seconds: int = Field(
        default=DEFAULT_PARSING_TIMEOUT_SECONDS,
        ge=MIN_PARSING_TIMEOUT_SECONDS,
        le=MAX_PARSING_TIMEOUT_SECONDS,
    )


class SearchCallBindingRequest(CallBindingRequest):
    request_timeout_seconds: int = Field(
        default=DEFAULT_SEARCH_TIMEOUT_SECONDS,
        ge=MIN_SEARCH_TIMEOUT_SECONDS,
        le=MAX_SEARCH_TIMEOUT_SECONDS,
    )


class CallBindingsRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    job_requirement_parsing: ParsingCallBindingRequest
    search_interpretation: SearchCallBindingRequest


class CandidateConfigurationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0, ge=0, le=1)
    max_output_tokens: int = Field(default=8192, ge=1024, le=16384)
    call_bindings: CallBindingsRequest

    @field_validator("model")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            message = "must not be blank"
            raise ValueError(message)
        return normalized

    def candidate(self) -> CandidateConfiguration:
        return CandidateConfiguration(
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            bindings=(
                CallTypeBinding(
                    call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                    prompt_version_id=self.call_bindings.job_requirement_parsing.prompt_version_id,
                    request_timeout_seconds=(
                        self.call_bindings.job_requirement_parsing.request_timeout_seconds
                    ),
                ),
                CallTypeBinding(
                    call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                    prompt_version_id=self.call_bindings.search_interpretation.prompt_version_id,
                    request_timeout_seconds=(
                        self.call_bindings.search_interpretation.request_timeout_seconds
                    ),
                ),
            ),
        )


@final
class CreateAttemptRequest(CandidateConfigurationRequest):
    expected_current_version_id: uuid.UUID


@final
class CopyAttemptRequest(BaseModel):
    expected_current_version_id: uuid.UUID


class CallBindingResponse(BaseModel):
    prompt_version_id: str
    request_timeout_seconds: int


@final
class ConfigurationVersionResponse(BaseModel):
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
    call_bindings: dict[str, CallBindingResponse | None]
    source_version_id: uuid.UUID | None
    source: str
    created_by: uuid.UUID | None
    created_at: datetime


@final
class PromptVersionResponse(BaseModel):
    id: str
    compatible_schema_version_id: str
    call_type: str
    sha256: str


@final
class SchemaSummaryResponse(BaseModel):
    id: str
    schema_id: str
    sha256: str
    field_catalog: dict[str, object]
    chinese_identity_values: list[str]
    output_limits: dict[str, int]


@final
class AttemptResponse(BaseModel):
    id: uuid.UUID
    status: str
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
class WorkspaceResponse(BaseModel):
    current: ConfigurationVersionResponse
    history: list[ConfigurationVersionResponse]
    prompt_versions: list[PromptVersionResponse]
    schema_versions: list[SchemaSummaryResponse]
    active_attempt: AttemptResponse | None


def _version_response(
    version: service.LlmConfigurationVersionView,
) -> ConfigurationVersionResponse:
    payload = dict(version.__dict__)
    payload["call_bindings"] = {
        call_type: None if binding is None else CallBindingResponse(**binding.__dict__)
        for call_type, binding in version.call_bindings.items()
    }
    return ConfigurationVersionResponse(**payload)


def _attempt_response(attempt: service.LlmConfigurationAttemptView) -> AttemptResponse:
    return AttemptResponse(**attempt.__dict__)


@router.get("/admin/llm-configuration")
async def read_llm_configuration(
    _admin: PlatformAdminDep,
    session: DbSession,
) -> WorkspaceResponse:
    workspace = await service.load_workspace(session)
    return WorkspaceResponse(
        current=_version_response(workspace.current),
        history=[_version_response(version) for version in workspace.history],
        prompt_versions=[
            PromptVersionResponse(**prompt.__dict__) for prompt in workspace.prompt_versions
        ],
        schema_versions=[
            SchemaSummaryResponse(**schema.__dict__) for schema in workspace.schema_versions
        ],
        active_attempt=(
            None
            if workspace.active_attempt is None
            else _attempt_response(workspace.active_attempt)
        ),
    )


@router.post(
    "/admin/llm-configuration-attempts",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def create_llm_configuration_attempt(
    payload: CreateAttemptRequest,
    admin: PlatformAdminDep,
    session: DbSession,
) -> AttemptResponse | JSONResponse:
    try:
        attempt = await service.create_attempt(
            session,
            candidate=payload.candidate(),
            expected_current_version_id=payload.expected_current_version_id,
            actor_id=admin.user.id,
        )
    except service.StaleCurrentConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except service.IncompatibleLlmAssetsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except service.ConfigChangeInProgressError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "attempt_id": str(error.attempt_id),
                "detail": service.CONFIG_CHANGE_IN_PROGRESS,
            },
        )
    return _attempt_response(attempt)


@router.post(
    "/admin/llm-configurations/{version_id}/copy-attempts",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def copy_llm_configuration_attempt(
    version_id: uuid.UUID,
    payload: CopyAttemptRequest,
    admin: PlatformAdminDep,
    session: DbSession,
) -> AttemptResponse | JSONResponse:
    try:
        attempt = await service.copy_version_as_attempt(
            session,
            version_id=version_id,
            expected_current_version_id=payload.expected_current_version_id,
            actor_id=admin.user.id,
        )
    except service.LlmConfigurationVersionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except service.StaleCurrentConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except service.IncompatibleLlmAssetsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except service.ConfigChangeInProgressError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "attempt_id": str(error.attempt_id),
                "detail": service.CONFIG_CHANGE_IN_PROGRESS,
            },
        )
    return _attempt_response(attempt)


@router.get("/admin/llm-configuration-attempts/{attempt_id}")
async def read_llm_configuration_attempt(
    attempt_id: uuid.UUID,
    _admin: PlatformAdminDep,
    session: DbSession,
) -> AttemptResponse:
    try:
        attempt = await service.get_attempt(session, attempt_id=attempt_id)
    except service.LlmConfigurationAttemptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _attempt_response(attempt)


@router.post("/admin/llm-configuration-attempts/{attempt_id}/cancel")
async def cancel_llm_configuration_attempt(
    attempt_id: uuid.UUID,
    admin: PlatformAdminDep,
    session: DbSession,
) -> AttemptResponse:
    try:
        attempt = await service.cancel_attempt(
            session,
            attempt_id=attempt_id,
            actor_id=admin.user.id,
        )
    except service.LlmConfigurationAttemptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _attempt_response(attempt)


@router.get("/admin/llm-configuration-attempts/{attempt_id}/events")
async def stream_llm_configuration_attempt_events(
    attempt_id: uuid.UUID,
    request: Request,
    _admin: PlatformAdminDep,
    session: DbSession,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        after_sequence = parse_last_event_id(last_event_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_last_event_id",
        ) from error
    try:
        _ = await service.get_attempt(session, attempt_id=attempt_id)
    except service.LlmConfigurationAttemptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    async def event_stream() -> AsyncIterator[str]:
        started_at = time.monotonic()
        last_heartbeat_at = started_at
        cursor = after_sequence
        while time.monotonic() - started_at < MAX_CONNECTION_SECONDS:
            if await request.is_disconnected():
                return
            events = await service.list_attempt_events(
                session,
                attempt_id=attempt_id,
                after_sequence=cursor,
            )
            for event in events:
                cursor = event.sequence_number
                data = {
                    "attempt_id": str(event.attempt_id),
                    "created_at": event.created_at.isoformat(),
                    "payload": event.payload,
                    "status": event.event_type,
                }
                yield encode_sse_event(
                    sequence_number=event.sequence_number,
                    event_type=event.event_type,
                    data=data,
                )
                if event.event_type in _TERMINAL_EVENTS:
                    return
            now = time.monotonic()
            if now - last_heartbeat_at >= HEARTBEAT_SECONDS:
                yield encode_sse_heartbeat()
                last_heartbeat_at = now
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )
