"""HTTP routes for job posting lifecycle, materials, and audit events."""

from __future__ import annotations

import uuid  # noqa: TC003 (pydantic resolves model annotations at runtime)
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import job_service, tenant_audit_service
from relationship_network_api.company_service import (
    COMPANY_ARCHIVED_DETAIL,
    COMPANY_NOT_FOUND_DETAIL,
    CompanyArchivedError,
    CompanyNotFoundError,
)
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    TenantContext,
    get_db_session,
    get_settings,
    require_permission,
    require_writable_permission,
)
from relationship_network_api.document_text import (
    DOCUMENT_TOO_LARGE_DETAIL,
    INVALID_DOCUMENT_DETAIL,
    MAX_DOCUMENT_BYTES,
    DocumentTooLargeError,
    InvalidDocumentError,
)
from relationship_network_api.job_service import (
    JOB_NOT_DRAFT_DETAIL,
    JOB_NOT_FOUND_DETAIL,
    JOB_QUOTA_EXCEEDED_DETAIL,
    JOB_STATUS_CONFLICT_DETAIL,
    REQUIREMENT_VERSION_REQUIRED_DETAIL,
    JobMaterialView,
    JobNotDraftError,
    JobNotFoundError,
    JobStatusConflictError,
    JobView,
    RequirementVersionRequiredError,
)
from relationship_network_api.models import JobStatus  # noqa: TC001
from relationship_network_api.object_storage_service import (
    ObjectStorage,
    ObjectStorageError,
    build_object_storage,
)
from relationship_network_api.tenant_audit_service import (
    TARGET_TYPE_JOB,
    TenantAuditEventView,
)
from relationship_network_api.usage_service import QuotaExceededError

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
JobsReadDep = Annotated[TenantContext, Depends(require_permission("jobs:read"))]
require_jobs_manage = require_writable_permission("jobs:manage")
JobsManageDep = Annotated[TenantContext, Depends(require_jobs_manage)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]


class CreateJobRequest(BaseModel):
    company_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=100_000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "title must not be blank"
            raise ValueError(msg)
        return stripped


class UpdateJobRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=100_000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "title must not be blank"
            raise ValueError(msg)
        return stripped


class JobResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str
    status: JobStatus
    created_at: str
    updated_at: str
    archived_at: str | None


class JobMaterialResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    extracted_text: str
    scan_status: str
    uploaded_by: uuid.UUID | None
    created_at: str


class TenantAuditEventResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    result: str
    detail: str
    created_at: str


def job_response(view: JobView) -> JobResponse:
    return JobResponse(
        id=view.id,
        company_id=view.company_id,
        title=view.title,
        description=view.description,
        status=view.status,
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
        archived_at=view.archived_at.isoformat() if view.archived_at else None,
    )


def material_response(view: JobMaterialView) -> JobMaterialResponse:
    return JobMaterialResponse(
        id=view.id,
        job_id=view.job_id,
        original_filename=view.original_filename,
        content_type=view.content_type,
        byte_size=view.byte_size,
        sha256=view.sha256,
        extracted_text=view.extracted_text,
        scan_status=view.scan_status,
        uploaded_by=view.uploaded_by,
        created_at=view.created_at.isoformat(),
    )


def audit_response(view: TenantAuditEventView) -> TenantAuditEventResponse:
    return TenantAuditEventResponse(
        id=view.id,
        actor_user_id=view.actor_user_id,
        action=view.action,
        target_type=view.target_type,
        target_id=view.target_id,
        result=view.result,
        detail=view.detail,
        created_at=view.created_at.isoformat(),
    )


def get_object_storage(settings: SettingsDep) -> ObjectStorage:
    return build_object_storage(settings)


ObjectStorageDep = Annotated[ObjectStorage, Depends(get_object_storage)]


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    context: JobsManageDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.create_job(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            company_id=body.company_id,
            title=body.title,
            description=body.description,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    except CompanyArchivedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=COMPANY_ARCHIVED_DETAIL,
        ) from error
    return job_response(view)


@router.get("/jobs")
async def list_jobs(
    context: JobsReadDep,
    session: DbSession,
    status_filter: Annotated[
        Literal["draft", "active", "closed", "archived"] | None,
        Query(alias="status"),
    ] = None,
    company_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[JobResponse]:
    views = await job_service.list_jobs(
        session,
        tenant_id=context.tenant_id,
        status=status_filter,
        company_id=company_id,
    )
    return [job_response(view) for view in views]


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.get_job(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    return job_response(view)


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: uuid.UUID,
    body: UpdateJobRequest,
    context: JobsManageDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.update_job(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            job_id=job_id,
            title=body.title,
            description=body.description,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except JobNotDraftError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_NOT_DRAFT_DETAIL,
        ) from error
    return job_response(view)


@router.post("/jobs/{job_id}/activate")
async def activate_job(
    job_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.activate_job(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except JobStatusConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_STATUS_CONFLICT_DETAIL,
        ) from error
    except RequirementVersionRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=REQUIREMENT_VERSION_REQUIRED_DETAIL,
        ) from error
    except CompanyArchivedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=COMPANY_ARCHIVED_DETAIL,
        ) from error
    except QuotaExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_QUOTA_EXCEEDED_DETAIL,
        ) from error
    return job_response(view)


@router.post("/jobs/{job_id}/close")
async def close_job(
    job_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.close_job(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except JobStatusConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_STATUS_CONFLICT_DETAIL,
        ) from error
    return job_response(view)


@router.post("/jobs/{job_id}/archive")
async def archive_job(
    job_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
) -> JobResponse:
    try:
        view = await job_service.archive_job(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except JobStatusConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_STATUS_CONFLICT_DETAIL,
        ) from error
    return job_response(view)


@router.post("/jobs/{job_id}/materials", status_code=status.HTTP_201_CREATED)
async def upload_job_material(
    job_id: uuid.UUID,
    context: JobsManageDep,
    session: DbSession,
    storage: ObjectStorageDep,
    file: Annotated[UploadFile, File()],
) -> JobMaterialResponse:
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    filename = file.filename or "upload.bin"
    try:
        view = await job_service.upload_material(
            session,
            storage=storage,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            job_id=job_id,
            filename=filename,
            data=data,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    except CompanyArchivedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=COMPANY_ARCHIVED_DETAIL,
        ) from error
    except JobNotDraftError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=JOB_NOT_DRAFT_DETAIL,
        ) from error
    except DocumentTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=DOCUMENT_TOO_LARGE_DETAIL,
        ) from error
    except InvalidDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_DOCUMENT_DETAIL,
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="object_storage_unavailable",
        ) from error
    return material_response(view)


@router.get("/jobs/{job_id}/materials")
async def list_job_materials(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> list[JobMaterialResponse]:
    try:
        views = await job_service.list_materials(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    return [material_response(view) for view in views]


@router.get("/jobs/{job_id}/materials/{material_id}/content")
async def download_job_material(
    job_id: uuid.UUID,
    material_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
    storage: ObjectStorageDep,
) -> StreamingResponse:
    try:
        material = await job_service.load_material_for_download(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
            material_id=material_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    try:
        stream = storage.stream_bytes(key=material.storage_key)
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="object_storage_unavailable",
        ) from error
    headers = {
        "Content-Disposition": f'attachment; filename="{material.original_filename}"',
    }
    return StreamingResponse(
        stream,
        media_type=material.content_type,
        headers=headers,
    )


@router.get("/jobs/{job_id}/events")
async def list_job_events(
    job_id: uuid.UUID,
    context: JobsReadDep,
    session: DbSession,
) -> list[TenantAuditEventResponse]:
    try:
        _ = await job_service.get_job(
            session,
            tenant_id=context.tenant_id,
            job_id=job_id,
        )
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND_DETAIL,
        ) from error
    events = await tenant_audit_service.list_events_for_target(
        session,
        tenant_id=context.tenant_id,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
    )
    return [audit_response(event) for event in events]
