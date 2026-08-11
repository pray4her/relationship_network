import uuid
from datetime import datetime
from typing import Annotated, Literal, final

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import llm_call_diagnostics_service as service
from relationship_network_api.auth_service import Authentication
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import get_db_session, get_settings, require_platform_admin

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
PlatformAdminDep = Annotated[Authentication, Depends(require_platform_admin)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
CallScope = Literal["platform", "tenant"]
CallType = Literal["config_probe", "job_requirement_parsing"]
CallOutcome = Literal["succeeded", "failed", "outcome_unknown", "late_response"]
MetadataStatus = Literal["available", "retry_scheduled", "unavailable"]


@final
class LlmCallSummaryResponse(BaseModel):
    id: uuid.UUID
    scope: str
    tenant_id: uuid.UUID | None
    call_type: str
    model: str
    request_number: int
    platform_attempt_id: uuid.UUID | None
    job_requirement_parsing_task_id: uuid.UUID | None
    outcome: str | None
    metadata_status: str | None
    raw_response_available: bool
    created_at: datetime


@final
class LlmCallListResponse(BaseModel):
    calls: list[LlmCallSummaryResponse]
    next_cursor: str | None


@final
class LlmCallCoreResponse(BaseModel):
    id: uuid.UUID
    scope: str
    tenant_id: uuid.UUID | None
    scope_key: str
    call_type: str
    platform_attempt_id: uuid.UUID | None
    job_requirement_parsing_task_id: uuid.UUID | None
    configuration_version_id: uuid.UUID | None
    input_snapshot_id: uuid.UUID | None
    correlation_call_id: uuid.UUID | None
    request_number: int
    model: str
    prompt_version_id: str
    prompt_sha256: str
    requirement_schema_version_id: str
    requirement_schema_sha256: str
    input_sources_summary: dict[str, object]
    input_sha256: str
    input_length: int
    parameters: dict[str, object]
    request_hash: str
    created_at: datetime


@final
class LlmCallOutcomeResponse(BaseModel):
    sequence_number: int
    outcome: str
    category: str
    provider_request_id: str | None
    actual_model: str | None
    actual_provider: str | None
    http_status: int | None
    duration_ms: int | None
    created_at: datetime


@final
class LlmCallMetadataResponse(BaseModel):
    sequence_number: int
    status: str
    generation_id: str | None
    actual_model: str | None
    actual_provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost: float | None
    source: str
    next_retry_at: datetime | None
    error_category: str
    created_at: datetime


@final
class LlmCallDetailResponse(BaseModel):
    call: LlmCallCoreResponse
    outcomes: list[LlmCallOutcomeResponse]
    metadata_events: list[LlmCallMetadataResponse]
    raw_response_available: bool
    raw_response_expires_at: datetime | None


@final
class RawResponseViewResponse(BaseModel):
    body: str
    encoding: str
    content_type: str | None
    http_status: int | None
    response_sequence: int
    created_at: datetime
    expires_at: datetime


@router.get("/admin/llm-calls")
async def list_llm_calls(  # noqa: PLR0913
    _admin: PlatformAdminDep,
    session: DbSession,
    call_scope: Annotated[CallScope | None, Query(alias="scope")] = None,
    call_type: CallType | None = None,
    outcome: CallOutcome | None = None,
    metadata_status: MetadataStatus | None = None,
    tenant_id: uuid.UUID | None = None,
    platform_attempt_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
) -> LlmCallListResponse:
    try:
        page = await service.list_calls(
            session,
            scope=call_scope,
            call_type=call_type,
            outcome=outcome,
            metadata_status=metadata_status,
            tenant_id=tenant_id,
            platform_attempt_id=platform_attempt_id,
            created_from=created_from,
            created_to=created_to,
            cursor=cursor,
        )
    except service.InvalidLlmCallCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return LlmCallListResponse(
        calls=[LlmCallSummaryResponse(**item.__dict__) for item in page.calls],
        next_cursor=page.next_cursor,
    )


@router.get("/admin/llm-calls/{call_id}")
async def read_llm_call(
    call_id: uuid.UUID,
    _admin: PlatformAdminDep,
    session: DbSession,
) -> LlmCallDetailResponse:
    try:
        detail = await service.get_call_detail(session, call_id=call_id)
    except service.LlmCallNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    call = detail.call
    return LlmCallDetailResponse(
        call=LlmCallCoreResponse(
            id=call.id,
            scope=call.scope,
            tenant_id=call.tenant_id,
            scope_key=call.scope_key,
            call_type=call.call_type,
            platform_attempt_id=call.platform_attempt_id,
            job_requirement_parsing_task_id=call.job_requirement_parsing_task_id,
            configuration_version_id=call.configuration_version_id,
            input_snapshot_id=call.input_snapshot_id,
            correlation_call_id=call.correlation_call_id,
            request_number=call.request_number,
            model=call.model,
            prompt_version_id=call.prompt_version_id,
            prompt_sha256=call.prompt_sha256,
            requirement_schema_version_id=call.requirement_schema_version_id,
            requirement_schema_sha256=call.requirement_schema_sha256,
            input_sources_summary=call.input_sources_summary,
            input_sha256=call.input_sha256,
            input_length=call.input_length,
            parameters=call.parameters,
            request_hash=call.request_hash,
            created_at=call.created_at,
        ),
        outcomes=[LlmCallOutcomeResponse(**event.__dict__) for event in detail.outcomes],
        metadata_events=[
            LlmCallMetadataResponse(**event.__dict__) for event in detail.metadata_events
        ],
        raw_response_available=detail.raw_response_available,
        raw_response_expires_at=detail.raw_response_expires_at,
    )


@router.post("/admin/llm-calls/{call_id}/raw-response")
async def view_llm_raw_response(
    call_id: uuid.UUID,
    admin: PlatformAdminDep,
    session: DbSession,
    settings: SettingsDep,
    response: Response,
) -> RawResponseViewResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        view = await service.view_raw_response(
            session,
            call_id=call_id,
            actor_id=admin.user.id,
            raw_keys_json=settings.llm_raw_response_keys.get_secret_value(),
            active_key_id=settings.llm_raw_response_active_key_id,
        )
    except service.LlmRawResponseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
            headers={"Cache-Control": "no-store"},
        ) from error
    except service.LlmRawResponseKeyUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
            headers={"Cache-Control": "no-store"},
        ) from error
    except service.LlmRawResponseDecryptionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
            headers={"Cache-Control": "no-store"},
        ) from error
    return RawResponseViewResponse(**view.__dict__)
