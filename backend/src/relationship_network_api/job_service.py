"""Job posting lifecycle: drafts, activation quota, closing, archival, materials."""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast, final

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from relationship_network_api import (
    company_service,
    tenant_audit_service,
    tenant_context,
    usage_service,
)
from relationship_network_api.company_service import CompanyArchivedError
from relationship_network_api.document_text import extract_text, validate_document
from relationship_network_api.models import (
    COMPANY_STATUS_ARCHIVED,
    JOB_STATUS_ACTIVE,
    JOB_STATUS_ARCHIVED,
    JOB_STATUS_CLOSED,
    JOB_STATUS_DRAFT,
    DocumentScanStatus,
    Job,
    JobMaterial,
    JobRequirementParsingTask,
    JobRequirementParsingTaskEvent,
    JobStatus,
)
from relationship_network_api.tenant_audit_service import (
    AUDIT_RESULT_SUCCESS,
    TARGET_TYPE_JOB,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

    from relationship_network_api.object_storage_service import ObjectStorage

JOB_NOT_FOUND_DETAIL: Final = "job_not_found"
JOB_NOT_DRAFT_DETAIL: Final = "job_not_draft"
JOB_STATUS_CONFLICT_DETAIL: Final = "job_status_conflict"
JOB_QUOTA_EXCEEDED_DETAIL: Final = "job_quota_exceeded"
REQUIREMENT_VERSION_REQUIRED_DETAIL: Final = "requirement_version_required"

ACTION_JOB_CREATE: Final = "job.create"
ACTION_JOB_UPDATE: Final = "job.update"
ACTION_JOB_ACTIVATE: Final = "job.activate"
ACTION_JOB_CLOSE: Final = "job.close"
ACTION_JOB_ARCHIVE: Final = "job.archive"
ACTION_JOB_MATERIAL_UPLOAD: Final = "job.material_upload"

_ALLOWED_TRANSITIONS: Final[Mapping[JobStatus, frozenset[JobStatus]]] = {
    JOB_STATUS_DRAFT: frozenset({JOB_STATUS_ACTIVE, JOB_STATUS_ARCHIVED}),
    JOB_STATUS_ACTIVE: frozenset({JOB_STATUS_CLOSED}),
    JOB_STATUS_CLOSED: frozenset({JOB_STATUS_ACTIVE, JOB_STATUS_ARCHIVED}),
    JOB_STATUS_ARCHIVED: frozenset(),
}


@final
class JobNotFoundError(Exception):
    """Raised when a job does not exist in the caller's tenant."""


@final
class JobNotDraftError(Exception):
    """Raised when editing or uploading material for a non-draft job."""


@final
class JobStatusConflictError(Exception):
    """Raised when a requested state transition is not allowed."""


@final
class RequirementVersionRequiredError(Exception):
    """Raised when activation is blocked because no confirmed requirement version exists."""


@final
@dataclass(frozen=True)
class JobView:
    """Public job facts returned to callers."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str
    status: JobStatus
    usage_reservation_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


@final
@dataclass(frozen=True)
class JobMaterialView:
    """Public facts for a stored job material."""

    id: uuid.UUID
    job_id: uuid.UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    extracted_text: str
    scan_status: DocumentScanStatus
    uploaded_by: uuid.UUID | None
    created_at: datetime


async def create_job(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    company_id: uuid.UUID,
    title: str,
    description: str = "",
) -> JobView:
    """Create a draft job under a company; drafts consume no quota."""
    await _ensure_company_writable(session, tenant_id=tenant_id, company_id=company_id)
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        tenant_id=tenant_id,
        company_id=company_id,
        title=title.strip(),
        description=description,
        status=JOB_STATUS_DRAFT,
    )
    session.add(job)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_JOB_CREATE,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=title.strip(),
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_job(session, tenant_id=tenant_id, job_id=job_id)


async def list_jobs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status: JobStatus | None = None,
    company_id: uuid.UUID | None = None,
) -> list[JobView]:
    """List jobs for the tenant, optionally filtered by status and company."""
    statement = select(Job).where(Job.tenant_id == tenant_id)
    if status is not None:
        statement = statement.where(Job.status == status)
    if company_id is not None:
        statement = statement.where(Job.company_id == company_id)
    statement = statement.order_by(Job.created_at.desc())
    result = await session.execute(statement)
    return [_view(job) for job in result.scalars()]


async def get_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> JobView:
    """Return one job in the tenant or raise JobNotFoundError."""
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    return _view(job)


async def update_job(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
    title: str | None = None,
    description: str | None = None,
) -> JobView:
    """Edit draft title and/or description; non-draft jobs are frozen."""
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    if job.status != JOB_STATUS_DRAFT:
        raise JobNotDraftError
    if title is not None:
        job.title = title.strip()
    if description is not None:
        job.description = description
    job.updated_at = datetime.now(UTC)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_JOB_UPDATE,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=job.title,
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_job(session, tenant_id=tenant_id, job_id=job_id)


async def activate_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> JobView:
    """Activate a draft or closed job, consuming one concurrent active_jobs seat.

    The idempotency key carries a per-activation nonce: reserve() returns the
    existing reservation for a reused key, which would resurrect a vacated
    seat on re-activation. Reserve commits mid-flow, wiping row locks and the
    RLS context, so the winner of concurrent activations is decided by a
    conditional UPDATE and the loser releases its reservation.
    """
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    _ensure_transition(job.status, to=JOB_STATUS_ACTIVE)
    if job.current_requirement_version_id is None:
        tenant_audit_service.record_event(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=ACTION_JOB_ACTIVATE,
            target_type=TARGET_TYPE_JOB,
            target_id=str(job_id),
            result=tenant_audit_service.AUDIT_RESULT_FAILURE,
            detail=REQUIREMENT_VERSION_REQUIRED_DETAIL,
        )
        await _commit(session)
        raise RequirementVersionRequiredError
    await _ensure_company_writable(session, tenant_id=tenant_id, company_id=job.company_id)
    reservation = await usage_service.reserve(
        session,
        tenant_id=tenant_id,
        metric="active_jobs",
        amount=1,
        idempotency_key=f"job:{job_id}:activate:{uuid.uuid4().hex}",
        reference_type="job",
        reference_id=str(job_id),
    )
    await tenant_context.set_tenant_context(session, tenant_id)
    try:
        result = cast(
            "CursorResult[tuple[()]]",
            await session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.tenant_id == tenant_id,
                    Job.status.in_((JOB_STATUS_DRAFT, JOB_STATUS_CLOSED)),
                    Job.current_requirement_version_id.is_not(None),
                )
                .values(
                    status=JOB_STATUS_ACTIVE,
                    usage_reservation_id=reservation.reservation_id,
                    updated_at=datetime.now(UTC),
                )
            ),
        )
        if result.rowcount != 1:
            # Raised inside the handler so the except path releases the reservation.
            raise JobStatusConflictError  # noqa: TRY301
        tenant_audit_service.record_event(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=ACTION_JOB_ACTIVATE,
            target_type=TARGET_TYPE_JOB,
            target_id=str(job_id),
            result=AUDIT_RESULT_SUCCESS,
            detail=job.title,
        )
        await session.flush()
        _ = await usage_service.confirm(
            session,
            tenant_id=tenant_id,
            reservation_id=reservation.reservation_id,
        )
    except Exception:
        await session.rollback()
        await tenant_context.set_tenant_context(session, tenant_id)
        with contextlib.suppress(usage_service.ReservationStateError):
            _ = await usage_service.release(
                session,
                tenant_id=tenant_id,
                reservation_id=reservation.reservation_id,
            )
        raise
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_job(session, tenant_id=tenant_id, job_id=job_id)


async def close_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> JobView:
    """Close an active job and vacate its active_jobs seat.

    Status is persisted before vacate so a vacate failure cannot leave a
    closed job's seat double-counted as freed; a failed vacate keeps the seat
    occupied until a retry succeeds. Closing is not idempotent.
    """
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id, for_update=True)
    _ensure_transition(job.status, to=JOB_STATUS_CLOSED)
    reservation_id = job.usage_reservation_id
    now = datetime.now(UTC)
    job.status = JOB_STATUS_CLOSED
    job.updated_at = now
    if job.legacy_requirement_exempt:
        job.legacy_requirement_exempt = False
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_JOB_CLOSE,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=job.title,
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
    return await get_job(session, tenant_id=tenant_id, job_id=job_id)


async def archive_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> JobView:
    """Archive a draft or closed job; archived is terminal and holds no seat."""
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id, for_update=True)
    _ensure_transition(job.status, to=JOB_STATUS_ARCHIVED)
    await _transition_requirement_task_for_archive(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
    )
    now = datetime.now(UTC)
    job.status = JOB_STATUS_ARCHIVED
    job.archived_at = now
    job.updated_at = now
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_JOB_ARCHIVE,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=job.title,
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_job(session, tenant_id=tenant_id, job_id=job_id)


async def _transition_requirement_task_for_archive(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    task = (
        await session.execute(
            select(JobRequirementParsingTask)
            .where(
                JobRequirementParsingTask.tenant_id == tenant_id,
                JobRequirementParsingTask.job_id == job_id,
                JobRequirementParsingTask.status.in_(
                    ("queued", "running", "retry_scheduled", "cancel_requested")
                ),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if task is None or task.status == "cancel_requested":
        return
    if task.status == "running":
        task.status = "cancel_requested"
    else:
        task.status = "cancelled"
        task.completed_at = datetime.now(UTC)
        task.next_attempt_at = None
    await session.flush()
    sequence_number = (
        int(
            (
                await session.execute(
                    select(
                        func.coalesce(func.max(JobRequirementParsingTaskEvent.sequence_number), 0)
                    ).where(JobRequirementParsingTaskEvent.task_id == task.id)
                )
            ).scalar_one()
        )
        + 1
    )
    session.add(
        JobRequirementParsingTaskEvent(
            task_id=task.id,
            sequence_number=sequence_number,
            tenant_id=tenant_id,
            event_type=task.status,
            payload={},
        )
    )


async def upload_material(  # noqa: PLR0913
    session: AsyncSession,
    *,
    storage: ObjectStorage,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    job_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> JobMaterialView:
    """Validate, store, and index a job material; only drafts accept uploads."""
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id, for_update=True)
    await _ensure_company_writable(session, tenant_id=tenant_id, company_id=job.company_id)
    if job.status != JOB_STATUS_DRAFT:
        raise JobNotDraftError
    validated = validate_document(filename=filename, data=data)
    material_id = uuid.uuid4()
    storage_key = (
        f"tenants/{tenant_id}/companies/{job.company_id}/jobs/{job_id}/materials/{material_id}"
    )
    storage.put_bytes(
        key=storage_key,
        data=validated.data,
        content_type=validated.content_type,
    )
    extracted = extract_text(validated)
    material = JobMaterial(
        id=material_id,
        tenant_id=tenant_id,
        job_id=job_id,
        original_filename=validated.original_filename,
        content_type=validated.content_type,
        byte_size=len(validated.data),
        storage_key=storage_key,
        sha256=validated.sha256,
        extracted_text=extracted,
        scan_status=validated.scan_status,
        uploaded_by=actor_user_id,
    )
    session.add(material)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_JOB_MATERIAL_UPLOAD,
        target_type=TARGET_TYPE_JOB,
        target_id=str(job_id),
        result=AUDIT_RESULT_SUCCESS,
        detail=validated.original_filename,
    )
    await _commit(session)
    await tenant_context.set_tenant_context(session, tenant_id)
    return await get_material(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        material_id=material_id,
    )


async def list_materials(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> list[JobMaterialView]:
    """List materials for a job; ensures the job exists in-tenant."""
    _ = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    result = await session.execute(
        select(JobMaterial)
        .where(
            JobMaterial.tenant_id == tenant_id,
            JobMaterial.job_id == job_id,
        )
        .order_by(JobMaterial.created_at.desc())
    )
    return [_material_view(material) for material in result.scalars()]


async def get_material(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    material_id: uuid.UUID,
) -> JobMaterialView:
    """Return one material metadata row or raise JobNotFoundError."""
    material = await _load_material(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        material_id=material_id,
    )
    return _material_view(material)


async def load_material_for_download(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    material_id: uuid.UUID,
) -> JobMaterial:
    """Load the ORM material row for streaming content through the API."""
    return await _load_material(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        material_id=material_id,
    )


async def _ensure_company_writable(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    company = await company_service.get_company(
        session,
        tenant_id=tenant_id,
        company_id=company_id,
    )
    if company.status == COMPANY_STATUS_ARCHIVED:
        raise CompanyArchivedError


def _ensure_transition(current: JobStatus, *, to: JobStatus) -> None:
    if to not in _ALLOWED_TRANSITIONS[current]:
        raise JobStatusConflictError


async def _load_job(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    for_update: bool = False,
) -> Job:
    statement = select(Job).where(
        Job.id == job_id,
        Job.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError
    return job


async def _load_material(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    material_id: uuid.UUID,
) -> JobMaterial:
    _ = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    material = (
        await session.execute(
            select(JobMaterial).where(
                JobMaterial.id == material_id,
                JobMaterial.job_id == job_id,
                JobMaterial.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if material is None:
        raise JobNotFoundError
    return material


def _view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        tenant_id=job.tenant_id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        status=job.status,
        usage_reservation_id=job.usage_reservation_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        archived_at=job.archived_at,
    )


def _material_view(material: JobMaterial) -> JobMaterialView:
    return JobMaterialView(
        id=material.id,
        job_id=material.job_id,
        original_filename=material.original_filename,
        content_type=material.content_type,
        byte_size=material.byte_size,
        sha256=material.sha256,
        extracted_text=material.extracted_text,
        scan_status=material.scan_status,
        uploaded_by=material.uploaded_by,
        created_at=material.created_at,
    )


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
