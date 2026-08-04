"""Company lifecycle: create, list, detail, edit, archive with quota and audit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_audit_service, tenant_context, usage_service
from relationship_network_api.document_text import (
    extract_text,
    validate_document,
)
from relationship_network_api.models import (
    COMPANY_STATUS_ACTIVE,
    COMPANY_STATUS_ARCHIVED,
    Company,
    CompanyDocument,
    CompanyStatus,
    DocumentScanStatus,
)
from relationship_network_api.object_storage_service import ObjectStorage
from relationship_network_api.tenant_audit_service import (
    AUDIT_RESULT_SUCCESS,
    TARGET_TYPE_COMPANY,
)
from relationship_network_api.usage_service import QuotaExceededError

COMPANY_NOT_FOUND_DETAIL: Final = "company_not_found"
COMPANY_ARCHIVED_DETAIL: Final = "company_archived"
COMPANY_QUOTA_EXCEEDED_DETAIL: Final = "company_quota_exceeded"

ACTION_COMPANY_CREATE: Final = "company.create"
ACTION_COMPANY_UPDATE: Final = "company.update"
ACTION_COMPANY_ARCHIVE: Final = "company.archive"
ACTION_COMPANY_UPLOAD: Final = "company.document_upload"


@final
class CompanyNotFoundError(Exception):
    """Raised when a company does not exist in the caller's tenant."""


@final
class CompanyArchivedError(Exception):
    """Raised when a mutation targets an archived company."""


@final
@dataclass(frozen=True)
class CompanyView:
    """Public company facts returned to callers."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    profile_text: str
    status: CompanyStatus
    usage_reservation_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


async def create_company(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    profile_text: str = "",
) -> CompanyView:
    """Create a company, consuming one concurrent companies seat."""
    company_id = uuid.uuid4()
    idempotency_key = f"company:{company_id}:create"
    try:
        reservation = await usage_service.reserve(
            session,
            tenant_id=tenant_id,
            metric="companies",
            amount=1,
            idempotency_key=idempotency_key,
            reference_type="company",
            reference_id=str(company_id),
        )
    except QuotaExceededError:
        raise
    await tenant_context.set_tenant_context(session, tenant_id)
    now = datetime.now(UTC)
    company = Company(
        id=company_id,
        tenant_id=tenant_id,
        name=name.strip(),
        profile_text=profile_text,
        status=COMPANY_STATUS_ACTIVE,
        usage_reservation_id=reservation.reservation_id,
        created_at=now,
        updated_at=now,
    )
    session.add(company)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_COMPANY_CREATE,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=name.strip(),
    )
    try:
        await session.flush()
        _ = await usage_service.confirm(
            session,
            tenant_id=tenant_id,
            reservation_id=reservation.reservation_id,
        )
    except Exception:
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        try:
            _ = await usage_service.release(
                session,
                tenant_id=tenant_id,
                reservation_id=reservation.reservation_id,
            )
        except usage_service.ReservationStateError:
            pass
        raise
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_company(session, tenant_id=tenant_id, company_id=company_id)


async def list_companies(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status: CompanyStatus | None = None,
) -> list[CompanyView]:
    """List companies for the tenant, optionally filtered by status."""
    statement = select(Company).where(Company.tenant_id == tenant_id)
    if status is not None:
        statement = statement.where(Company.status == status)
    statement = statement.order_by(Company.created_at.desc())
    result = await session.execute(statement)
    return [_view(company) for company in result.scalars()]


async def get_company(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
) -> CompanyView:
    """Return one company in the tenant or raise CompanyNotFoundError."""
    company = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    return _view(company)


async def update_company(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    company_id: uuid.UUID,
    name: str | None = None,
    profile_text: str | None = None,
) -> CompanyView:
    """Edit company name and/or profile text; archived companies cannot change."""
    company = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    if company.status == COMPANY_STATUS_ARCHIVED:
        raise CompanyArchivedError
    if name is not None:
        company.name = name.strip()
    if profile_text is not None:
        company.profile_text = profile_text
    company.updated_at = datetime.now(UTC)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_COMPANY_UPDATE,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=company.name,
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_company(session, tenant_id=tenant_id, company_id=company_id)


@final
@dataclass(frozen=True)
class CompanyDocumentView:
    """Public facts for a stored company document."""

    id: uuid.UUID
    company_id: uuid.UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    extracted_text: str
    scan_status: DocumentScanStatus
    uploaded_by: uuid.UUID | None
    created_at: datetime


async def archive_company(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    company_id: uuid.UUID,
) -> CompanyView:
    """Archive a company and vacate its concurrent companies seat.

    Status is persisted before vacate so a vacate failure cannot leave an
    active company with a freed seat. A failed vacate leaves the company
    archived while still counting against quota until a retry succeeds.
    """
    company = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    if company.status == COMPANY_STATUS_ARCHIVED:
        return _view(company)
    reservation_id = company.usage_reservation_id
    now = datetime.now(UTC)
    company.status = COMPANY_STATUS_ARCHIVED
    company.archived_at = now
    company.updated_at = now
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_COMPANY_ARCHIVE,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=company.name,
    )
    await _commit(session)
    if reservation_id is not None:
        await tenant_context.set_tenant_context(session, tenant_id)
        _ = await usage_service.vacate_confirmed(
            session,
            tenant_id=tenant_id,
            reservation_id=reservation_id,
        )
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_company(session, tenant_id=tenant_id, company_id=company_id)


async def upload_document(
    session: AsyncSession,
    *,
    storage: ObjectStorage,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    company_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> CompanyDocumentView:
    """Validate, store, and index a company profile document."""
    company = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    if company.status == COMPANY_STATUS_ARCHIVED:
        raise CompanyArchivedError
    validated = validate_document(filename=filename, data=data)
    document_id = uuid.uuid4()
    storage_key = f"tenants/{tenant_id}/companies/{company_id}/documents/{document_id}"
    storage.put_bytes(
        key=storage_key,
        data=validated.data,
        content_type=validated.content_type,
    )
    extracted = extract_text(validated)
    document = CompanyDocument(
        id=document_id,
        tenant_id=tenant_id,
        company_id=company_id,
        original_filename=validated.original_filename,
        content_type=validated.content_type,
        byte_size=len(validated.data),
        storage_key=storage_key,
        sha256=validated.sha256,
        extracted_text=extracted,
        scan_status=validated.scan_status,
        uploaded_by=actor_user_id,
    )
    session.add(document)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_COMPANY_UPLOAD,
        target_type=TARGET_TYPE_COMPANY,
        target_id=str(company_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=validated.original_filename,
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_document(
        session,
        tenant_id=tenant_id,
        company_id=company_id,
        document_id=document_id,
    )


async def list_documents(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
) -> list[CompanyDocumentView]:
    """List documents for a company; ensures the company exists in-tenant."""
    _ = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    result = await session.execute(
        select(CompanyDocument)
        .where(
            CompanyDocument.tenant_id == tenant_id,
            CompanyDocument.company_id == company_id,
        )
        .order_by(CompanyDocument.created_at.desc())
    )
    return [_document_view(document) for document in result.scalars()]


async def get_document(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> CompanyDocumentView:
    """Return one document metadata row or raise CompanyNotFoundError."""
    document = await _load_document(
        session,
        tenant_id=tenant_id,
        company_id=company_id,
        document_id=document_id,
    )
    return _document_view(document)


async def load_document_for_download(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> CompanyDocument:
    """Load the ORM document row for streaming content through the API."""
    return await _load_document(
        session,
        tenant_id=tenant_id,
        company_id=company_id,
        document_id=document_id,
    )


async def _load_company(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
) -> Company:
    company = (
        await session.execute(
            select(Company).where(
                Company.id == company_id,
                Company.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise CompanyNotFoundError
    return company


async def _load_document(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> CompanyDocument:
    _ = await _load_company(session, tenant_id=tenant_id, company_id=company_id)
    document = (
        await session.execute(
            select(CompanyDocument).where(
                CompanyDocument.id == document_id,
                CompanyDocument.company_id == company_id,
                CompanyDocument.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise CompanyNotFoundError
    return document


def _view(company: Company) -> CompanyView:
    return CompanyView(
        id=company.id,
        tenant_id=company.tenant_id,
        name=company.name,
        profile_text=company.profile_text,
        status=company.status,
        usage_reservation_id=company.usage_reservation_id,
        created_at=company.created_at,
        updated_at=company.updated_at,
        archived_at=company.archived_at,
    )


def _document_view(document: CompanyDocument) -> CompanyDocumentView:
    return CompanyDocumentView(
        id=document.id,
        company_id=document.company_id,
        original_filename=document.original_filename,
        content_type=document.content_type,
        byte_size=document.byte_size,
        sha256=document.sha256,
        extracted_text=document.extracted_text,
        scan_status=document.scan_status,
        uploaded_by=document.uploaded_by,
        created_at=document.created_at,
    )


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
