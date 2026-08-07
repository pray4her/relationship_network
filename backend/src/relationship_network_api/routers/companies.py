"""HTTP routes for company lifecycle, documents, and audit events."""

from __future__ import annotations

import uuid  # noqa: TC003 (pydantic resolves model annotations at runtime)
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import company_service, tenant_audit_service
from relationship_network_api.company_service import (
    COMPANY_ARCHIVED_DETAIL,
    COMPANY_NOT_FOUND_DETAIL,
    COMPANY_QUOTA_EXCEEDED_DETAIL,
    CompanyArchivedError,
    CompanyDocumentView,
    CompanyNotFoundError,
    CompanyView,
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
from relationship_network_api.models import CompanyStatus  # noqa: TC001
from relationship_network_api.object_storage_service import (
    ObjectStorage,
    ObjectStorageError,
    build_object_storage,
)
from relationship_network_api.tenant_audit_service import (
    TARGET_TYPE_COMPANY,
    TenantAuditEventView,
)
from relationship_network_api.usage_service import QuotaExceededError

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CompaniesReadDep = Annotated[TenantContext, Depends(require_permission("companies:read"))]
require_companies_manage = require_writable_permission("companies:manage")
CompaniesManageDep = Annotated[TenantContext, Depends(require_companies_manage)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]


class CreateCompanyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    profile_text: str = Field(default="", max_length=100_000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "name must not be blank"
            raise ValueError(msg)
        return stripped


class UpdateCompanyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    profile_text: str | None = Field(default=None, max_length=100_000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "name must not be blank"
            raise ValueError(msg)
        return stripped


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    profile_text: str
    status: CompanyStatus
    created_at: str
    updated_at: str
    archived_at: str | None


class CompanyDocumentResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
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


def company_response(view: CompanyView) -> CompanyResponse:
    return CompanyResponse(
        id=view.id,
        name=view.name,
        profile_text=view.profile_text,
        status=view.status,
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
        archived_at=view.archived_at.isoformat() if view.archived_at else None,
    )


def document_response(view: CompanyDocumentView) -> CompanyDocumentResponse:
    return CompanyDocumentResponse(
        id=view.id,
        company_id=view.company_id,
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


@router.post("/companies", status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CreateCompanyRequest,
    context: CompaniesManageDep,
    session: DbSession,
) -> CompanyResponse:
    try:
        view = await company_service.create_company(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            name=body.name,
            profile_text=body.profile_text,
        )
    except QuotaExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=COMPANY_QUOTA_EXCEEDED_DETAIL,
        ) from error
    return company_response(view)


@router.get("/companies")
async def list_companies(
    context: CompaniesReadDep,
    session: DbSession,
    status_filter: Annotated[
        Literal["active", "archived"] | None,
        Query(alias="status"),
    ] = None,
) -> list[CompanyResponse]:
    views = await company_service.list_companies(
        session,
        tenant_id=context.tenant_id,
        status=status_filter,
    )
    return [company_response(view) for view in views]


@router.get("/companies/{company_id}")
async def get_company(
    company_id: uuid.UUID,
    context: CompaniesReadDep,
    session: DbSession,
) -> CompanyResponse:
    try:
        view = await company_service.get_company(
            session,
            tenant_id=context.tenant_id,
            company_id=company_id,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    return company_response(view)


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: uuid.UUID,
    body: UpdateCompanyRequest,
    context: CompaniesManageDep,
    session: DbSession,
) -> CompanyResponse:
    try:
        view = await company_service.update_company(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            company_id=company_id,
            name=body.name,
            profile_text=body.profile_text,
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
    return company_response(view)


@router.post("/companies/{company_id}/archive")
async def archive_company(
    company_id: uuid.UUID,
    context: CompaniesManageDep,
    session: DbSession,
) -> CompanyResponse:
    try:
        view = await company_service.archive_company(
            session,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            company_id=company_id,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    return company_response(view)


@router.post("/companies/{company_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_company_document(
    company_id: uuid.UUID,
    context: CompaniesManageDep,
    session: DbSession,
    storage: ObjectStorageDep,
    file: Annotated[UploadFile, File()],
) -> CompanyDocumentResponse:
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    filename = file.filename or "upload.bin"
    try:
        view = await company_service.upload_document(
            session,
            storage=storage,
            tenant_id=context.tenant_id,
            actor_user_id=context.authentication.user.id,
            company_id=company_id,
            filename=filename,
            data=data,
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
    return document_response(view)


@router.get("/companies/{company_id}/documents")
async def list_company_documents(
    company_id: uuid.UUID,
    context: CompaniesReadDep,
    session: DbSession,
) -> list[CompanyDocumentResponse]:
    try:
        views = await company_service.list_documents(
            session,
            tenant_id=context.tenant_id,
            company_id=company_id,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    return [document_response(view) for view in views]


@router.get("/companies/{company_id}/documents/{document_id}/content")
async def download_company_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    context: CompaniesReadDep,
    session: DbSession,
    storage: ObjectStorageDep,
) -> StreamingResponse:
    try:
        document = await company_service.load_document_for_download(
            session,
            tenant_id=context.tenant_id,
            company_id=company_id,
            document_id=document_id,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    try:
        stream = storage.stream_bytes(key=document.storage_key)
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="object_storage_unavailable",
        ) from error
    headers = {
        "Content-Disposition": f'attachment; filename="{document.original_filename}"',
    }
    return StreamingResponse(
        stream,
        media_type=document.content_type,
        headers=headers,
    )


@router.get("/companies/{company_id}/events")
async def list_company_events(
    company_id: uuid.UUID,
    context: CompaniesReadDep,
    session: DbSession,
) -> list[TenantAuditEventResponse]:
    try:
        _ = await company_service.get_company(
            session,
            tenant_id=context.tenant_id,
            company_id=company_id,
        )
    except CompanyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COMPANY_NOT_FOUND_DETAIL,
        ) from error
    events = await tenant_audit_service.list_events_for_target(
        session,
        tenant_id=context.tenant_id,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
    )
    return [audit_response(event) for event in events]
