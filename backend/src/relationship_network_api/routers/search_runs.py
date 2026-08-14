"""Tenant HTTP boundary for natural-language search runs."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import search_run_service as service
from relationship_network_api import tenant_audit_service, usage_service
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    PERMISSION_DENIED_DETAIL,
    SUBSCRIPTION_READ_ONLY_DETAIL,
    TenantContext,
    get_db_session,
    get_settings,
    get_tenant_context,
    require_permission,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
SearchReadDep = Annotated[TenantContext, Depends(require_permission("search:read"))]

AUDIT_ACTION_WRITE_DENIED = "search.run_denied"
AUDIT_TARGET_SEARCH = "natural_language_search"


async def require_search_run_audited(
    session: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    """Require ``search:run`` on a writable tenant, auditing authenticated denials.

    Only denials for an authenticated member inside their own tenant are
    recorded; anonymous requests and cross-tenant probes hidden by RLS never
    produce audit entries that could leak target existence.
    """
    detail: str | None = None
    if "search:run" not in context.permissions:
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
            target_type=AUDIT_TARGET_SEARCH,
            target_id="",
            result=tenant_audit_service.AUDIT_RESULT_FAILURE,
            detail=detail,
        )
        await session.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return context


SearchRunDep = Annotated[TenantContext, Depends(require_search_run_audited)]


class CreateSearchRunRequest(BaseModel):
    utterance: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=100)


class SearchHitSnapshotResponse(BaseModel):
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


class SearchRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    failure_reason: str | None
    utterance: str
    utterance_length: int
    idempotency_key: str
    llm_configuration_version_id: uuid.UUID
    search_contract_version: str
    data_version: str | None
    request_id: str | None
    has_research_topic: bool
    search_interpretation: dict[str, object] | None
    created_at: str


class SearchRunListResponse(BaseModel):
    runs: list[SearchRunResponse]
    next_cursor: str | None


class SearchRunDetailResponse(BaseModel):
    run: SearchRunResponse
    hits: list[SearchHitSnapshotResponse]
    next_cursor: str | None
    total: int
    sorted_by: str
    left_relevance_order: bool


def _run_response(view: service.SearchRunView) -> SearchRunResponse:
    return SearchRunResponse(
        id=view.id,
        status=view.status,
        failure_reason=view.failure_reason,
        utterance=view.utterance,
        utterance_length=view.utterance_length,
        idempotency_key=view.idempotency_key,
        llm_configuration_version_id=view.llm_configuration_version_id,
        search_contract_version=view.search_contract_version,
        data_version=view.data_version,
        request_id=view.request_id,
        has_research_topic=view.has_research_topic,
        search_interpretation=view.search_interpretation,
        created_at=view.created_at.isoformat(),
    )


def _hit_response(view: service.SearchHitSnapshotView) -> SearchHitSnapshotResponse:
    return SearchHitSnapshotResponse(
        id=view.id,
        local_talent_id=view.local_talent_id,
        canonical_person_id=view.canonical_person_id,
        display_name=view.display_name,
        current_affiliation=view.current_affiliation,
        country=view.country,
        chinese_identity=view.chinese_identity,
        h_index=view.h_index,
        total_citations=view.total_citations,
        qs_top200_rank=view.qs_top200_rank,
        world_top500_rank=view.world_top500_rank,
        has_contact=view.has_contact,
        data_version=view.data_version,
        hit_publications=view.hit_publications,
        semantic_score=view.semantic_score,
        sort_position=view.sort_position,
    )


def _http_error(error: service.SearchRunError) -> HTTPException:  # noqa: PLR0911
    if isinstance(error, service.InvalidUtteranceError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error.detail)
    if isinstance(error, service.SearchIdempotencyConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.detail)
    if isinstance(error, service.SearchCreationRateLimitedError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error.detail)
    if isinstance(error, service.SearchInProgressError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error.detail)
    if isinstance(error, service.SearchQuotaExceededError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.detail)
    if isinstance(error, service.SearchRunNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.detail)
    if isinstance(error, service.InvalidSortError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error.detail)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.detail)


@router.post("/search/runs", status_code=status.HTTP_201_CREATED)
async def create_search_run(
    body: CreateSearchRunRequest,
    _context: SearchRunDep,
    settings: SettingsDep,
) -> SearchRunResponse:
    try:
        view = await service.run_search(
            settings=settings,
            tenant_id=_context.tenant_id,
            actor_user_id=_context.authentication.user.id,
            utterance=body.utterance,
            idempotency_key=body.idempotency_key,
        )
    except service.SearchRunError as error:
        raise _http_error(error) from None
    return _run_response(view)


@router.get("/search/runs")
async def list_search_runs(
    _context: SearchReadDep,
    session: DbSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> SearchRunListResponse:
    page = await service.list_runs(
        session,
        tenant_id=_context.tenant_id,
        cursor=cursor,
        limit=limit,
    )
    return SearchRunListResponse(
        runs=[_run_response(run) for run in page.runs],
        next_cursor=page.next_cursor,
    )


@router.get("/search/runs/{run_id}")
async def get_search_run(
    run_id: uuid.UUID,
    _context: SearchReadDep,
    session: DbSession,
    sort: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> SearchRunDetailResponse:
    try:
        detail = await service.get_run(
            session,
            tenant_id=_context.tenant_id,
            run_id=run_id,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
    except service.SearchRunError as error:
        raise _http_error(error) from None
    return SearchRunDetailResponse(
        run=_run_response(detail.run),
        hits=[_hit_response(hit) for hit in detail.hits],
        next_cursor=detail.next_cursor,
        total=detail.total,
        sorted_by=detail.sorted_by,
        left_relevance_order=detail.left_relevance_order,
    )
