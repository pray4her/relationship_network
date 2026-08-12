"""Integration tests for job lifecycle, activation quota, materials, and RLS."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from relationship_network_api.document_text import MAX_DOCUMENT_BYTES
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    Company,
    Job,
    JobMaterial,
    JobRequirementDraft,
    JobRequirementVersion,
    TenantAuditEvent,
)
from relationship_network_api.tenant_context import set_tenant_context
from relationship_network_api.usage_service import get_usage_summary

from .conftest import Stack, unique_email

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import CursorResult

# Requires local PostgreSQL (+ MinIO for material upload) with alembic head applied.


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_owner(stack: Stack, client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "职位租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id


async def create_company(client: AsyncClient) -> uuid.UUID:
    created = await client.post("/companies", json={"name": "用人企业"})
    assert created.status_code == 201
    return uuid.UUID(created.json()["id"])


async def create_draft_job(client: AsyncClient, company_id: uuid.UUID, title: str) -> uuid.UUID:
    created = await client.post(
        "/jobs",
        json={"company_id": str(company_id), "title": title, "description": "职责描述"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    return uuid.UUID(body["id"])


async def seed_requirement_version(
    stack: Stack,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert a minimal confirmed requirement version so activation gates can pass."""
    draft_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result_json: dict[str, object] = {
        "hard_conditions": [],
        "preference_conditions": [],
        "research_topic_query": {
            "value": "seeded topic",
            "model_value": "seeded topic",
            "last_modified_by": None,
            "last_modified_at": None,
        },
        "unsupported_conditions": [],
        "source_conflicts": [],
        "removed_facts": [],
    }
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        session.add(
            JobRequirementDraft(
                id=draft_id,
                tenant_id=tenant_id,
                job_id=job_id,
                task_id=None,
                input_snapshot_id=None,
                source_version_id=None,
                requirement_schema_version_id=manifest.JOB_REQUIREMENT_SCHEMA_V2.id,
                status="confirmed",
                revision=1,
                result_json=result_json,
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
        )
        await session.flush()
        session.add(
            JobRequirementVersion(
                id=version_id,
                tenant_id=tenant_id,
                job_id=job_id,
                version_number=1,
                requirement_schema_version_id=manifest.JOB_REQUIREMENT_SCHEMA_V2.id,
                result_json=result_json,
                draft_id=draft_id,
                input_snapshot_id=None,
                source_version_id=None,
                confirmed_by=actor_user_id,
            )
        )
        await session.flush()
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.current_requirement_version_id = version_id
        await session.commit()
    return version_id


async def active_jobs_used(stack: Stack, tenant_id: uuid.UUID) -> int:
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        summary = await get_usage_summary(session, tenant_id=tenant_id)
    metric = next(item for item in summary.metrics if item.metric == "active_jobs")
    return metric.used


@pytest.mark.anyio
@pytest.mark.integration
async def test_job_lifecycle_quota_and_audit(  # noqa: PLR0915 (sequential lifecycle story)
    stack: Stack,
    client: AsyncClient,
) -> None:
    tenant_id = await register_owner(stack, client)
    company_id = await create_company(client)

    # Drafts are unlimited: trial caps companies at 1 but allows three drafts.
    job_1 = await create_draft_job(client, company_id, "后端工程师")
    job_2 = await create_draft_job(client, company_id, "前端工程师")
    job_3 = await create_draft_job(client, company_id, "数据工程师")

    updated = await client.patch(
        f"/jobs/{job_1}",
        json={"title": "高级后端工程师", "description": "负责 API 与数据管道"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "高级后端工程师"

    upload = await client.post(
        f"/jobs/{job_1}/materials",
        files={"file": ("jd.txt", b"job description body", "text/plain")},
    )
    assert upload.status_code == 201
    material = upload.json()
    assert material["extracted_text"] == "job description body"
    assert material["scan_status"] == "content_checked"

    invalid = await client.post(
        f"/jobs/{job_1}/materials",
        files={"file": ("jd.exe", b"not a document", "application/octet-stream")},
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "invalid_document"}

    oversized = await client.post(
        f"/jobs/{job_1}/materials",
        files={"file": ("big.txt", b"x" * (MAX_DOCUMENT_BYTES + 1), "text/plain")},
    )
    assert oversized.status_code == 413
    assert oversized.json() == {"detail": "document_too_large"}

    # Trial allows two active jobs.
    await seed_requirement_version(stack, tenant_id=tenant_id, job_id=job_1)
    await seed_requirement_version(stack, tenant_id=tenant_id, job_id=job_2)
    await seed_requirement_version(stack, tenant_id=tenant_id, job_id=job_3)
    first = await client.post(f"/jobs/{job_1}/activate")
    assert first.status_code == 200
    assert first.json()["status"] == "active"
    repeat = await client.post(f"/jobs/{job_1}/activate")
    assert repeat.status_code == 409
    assert repeat.json() == {"detail": "job_status_conflict"}

    second = await client.post(f"/jobs/{job_2}/activate")
    assert second.status_code == 200
    blocked = await client.post(f"/jobs/{job_3}/activate")
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "job_quota_exceeded"}
    assert await active_jobs_used(stack, tenant_id) == 2

    # Activated jobs are frozen for edits and uploads.
    frozen_edit = await client.patch(f"/jobs/{job_1}", json={"title": "改名"})
    assert frozen_edit.status_code == 409
    assert frozen_edit.json() == {"detail": "job_not_draft"}
    frozen_upload = await client.post(
        f"/jobs/{job_1}/materials",
        files={"file": ("late.txt", b"late material", "text/plain")},
    )
    assert frozen_upload.status_code == 409
    assert frozen_upload.json() == {"detail": "job_not_draft"}

    # Closing frees the seat; closing twice conflicts (not idempotent).
    closed = await client.post(f"/jobs/{job_1}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    closed_again = await client.post(f"/jobs/{job_1}/close")
    assert closed_again.status_code == 409
    assert closed_again.json() == {"detail": "job_status_conflict"}

    third = await client.post(f"/jobs/{job_3}/activate")
    assert third.status_code == 200

    # Re-activation after close must reserve a fresh seat (nonce key regression).
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        first_reservation = (
            (await session.execute(select(Job).where(Job.id == job_1)))
            .scalar_one()
            .usage_reservation_id
        )
    closed_second = await client.post(f"/jobs/{job_2}/close")
    assert closed_second.status_code == 200
    reactivated = await client.post(f"/jobs/{job_1}/activate")
    assert reactivated.status_code == 200
    assert await active_jobs_used(stack, tenant_id) == 2
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        second_reservation = (
            (await session.execute(select(Job).where(Job.id == job_1)))
            .scalar_one()
            .usage_reservation_id
        )
    assert second_reservation is not None
    assert second_reservation != first_reservation

    # Archival rules: active must close first; archived is terminal.
    archive_active = await client.post(f"/jobs/{job_3}/archive")
    assert archive_active.status_code == 409
    assert archive_active.json() == {"detail": "job_status_conflict"}
    job_4 = await create_draft_job(client, company_id, "测试工程师")
    archived = await client.post(f"/jobs/{job_4}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    archived_again = await client.post(f"/jobs/{job_4}/archive")
    assert archived_again.status_code == 409
    assert archived_again.json() == {"detail": "job_status_conflict"}

    events = await client.get(f"/jobs/{job_1}/events")
    assert events.status_code == 200
    actions = {event["action"] for event in events.json()}
    assert {
        "job.create",
        "job.update",
        "job.activate",
        "job.close",
        "job.material_upload",
    } <= actions

    download = await client.get(f"/jobs/{job_1}/materials/{material['id']}/content")
    assert download.status_code == 200
    assert download.content == b"job description body"
    assert "attachment" in download.headers.get("content-disposition", "")

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        audit_rows = (
            (
                await session.execute(
                    select(TenantAuditEvent).where(
                        TenantAuditEvent.tenant_id == tenant_id,
                        TenantAuditEvent.target_id == str(job_4),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(row.action == "job.archive" for row in audit_rows)


@pytest.mark.anyio
@pytest.mark.integration
async def test_job_rls_blocks_cross_tenant_access(stack: Stack, client: AsyncClient) -> None:
    tenant_a = await register_owner(stack, client)
    company_a = await create_company(client)
    job_a = await create_draft_job(client, company_a, "A 的职位")
    upload = await client.post(
        f"/jobs/{job_a}/materials",
        files={"file": ("a.txt", b"tenant a material", "text/plain")},
    )
    assert upload.status_code == 201
    material_a = uuid.UUID(upload.json()["id"])

    # Switch to tenant B by registering (new session cookie)
    _ = await register_owner(stack, client)

    missing = await client.get(f"/jobs/{job_a}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "job_not_found"}
    missing_materials = await client.get(f"/jobs/{job_a}/materials")
    assert missing_materials.status_code == 404
    missing_content = await client.get(f"/jobs/{job_a}/materials/{material_a}/content")
    assert missing_content.status_code == 404

    tenant_b = stack.tenant_ids[-1]
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        visible_jobs = (await session.execute(select(Job.id))).scalars().all()
        assert job_a not in visible_jobs
        visible_materials = (await session.execute(select(JobMaterial.id))).scalars().all()
        assert material_a not in visible_materials

        session.add(
            Job(
                id=uuid.uuid4(),
                tenant_id=tenant_a,
                company_id=company_a,
                title="越权写入",
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

        result = cast(
            "CursorResult[tuple[()]]",
            await session.execute(
                text("UPDATE jobs SET title = 'stolen' WHERE id = :id"),
                {"id": job_a},
            ),
        )
        assert result.rowcount == 0

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        visible = (
            (await session.execute(select(Company.id).where(Company.tenant_id == tenant_a)))
            .scalars()
            .all()
        )
        assert company_a in visible


@pytest.mark.anyio
@pytest.mark.integration
async def test_job_guards_on_archived_company(stack: Stack, client: AsyncClient) -> None:
    tenant_id = await register_owner(stack, client)
    company_id = await create_company(client)
    draft_job = await create_draft_job(client, company_id, "归档前的草稿")
    await seed_requirement_version(stack, tenant_id=tenant_id, job_id=draft_job)

    archived = await client.post(f"/companies/{company_id}/archive")
    assert archived.status_code == 200

    blocked_create = await client.post(
        "/jobs",
        json={"company_id": str(company_id), "title": "新职位"},
    )
    assert blocked_create.status_code == 409
    assert blocked_create.json() == {"detail": "company_archived"}

    blocked_activate = await client.post(f"/jobs/{draft_job}/activate")
    assert blocked_activate.status_code == 409
    assert blocked_activate.json() == {"detail": "company_archived"}

    blocked_upload = await client.post(
        f"/jobs/{draft_job}/materials",
        files={"file": ("jd.txt", b"blocked material", "text/plain")},
    )
    assert blocked_upload.status_code == 409
    assert blocked_upload.json() == {"detail": "company_archived"}
