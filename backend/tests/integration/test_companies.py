"""Integration tests for company lifecycle, quota, audit, and RLS."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from relationship_network_api.models import Company, TenantAuditEvent
from relationship_network_api.tenant_context import set_tenant_context
from relationship_network_api.usage_service import get_usage_summary

from .conftest import Stack, unique_email

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import CursorResult

# Requires local PostgreSQL (+ MinIO for document upload) with alembic head applied.


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
            "display_name": "企业租户主",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id


@pytest.mark.anyio
@pytest.mark.integration
async def test_company_lifecycle_quota_and_audit(stack: Stack, client: AsyncClient) -> None:
    tenant_id = await register_owner(stack, client)

    created = await client.post(
        "/companies",
        json={"name": "首家企业", "profile_text": "简介文本"},
    )
    assert created.status_code == 201
    company = created.json()
    company_id = company["id"]
    assert company["status"] == "active"

    # Trial allows only one company
    blocked = await client.post("/companies", json={"name": "第二家"})
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "company_quota_exceeded"}

    listed = await client.get("/companies")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/companies/{company_id}",
        json={"name": "首家企业已更名", "profile_text": "更新简介"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "首家企业已更名"

    upload = await client.post(
        f"/companies/{company_id}/documents",
        files={"file": ("profile.txt", b"company profile body", "text/plain")},
    )
    assert upload.status_code == 201
    document = upload.json()
    assert document["extracted_text"] == "company profile body"
    assert document["scan_status"] == "content_checked"

    events = await client.get(f"/companies/{company_id}/events")
    assert events.status_code == 200
    actions = {event["action"] for event in events.json()}
    assert "company.create" in actions
    assert "company.update" in actions
    assert "company.document_upload" in actions

    archived = await client.post(f"/companies/{company_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    # Archiving frees the concurrent seat so another company can be created
    second = await client.post("/companies", json={"name": "第二家企业"})
    assert second.status_code == 201

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        summary = await get_usage_summary(session, tenant_id=tenant_id)
        companies = next(metric for metric in summary.metrics if metric.metric == "companies")
        assert companies.used == 1
        assert companies.remaining == 0

        audit_rows = (
            (
                await session.execute(
                    select(TenantAuditEvent).where(
                        TenantAuditEvent.tenant_id == tenant_id,
                        TenantAuditEvent.target_id == company_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(row.action == "company.archive" for row in audit_rows)


@pytest.mark.anyio
@pytest.mark.integration
async def test_company_rls_blocks_cross_tenant_access(stack: Stack, client: AsyncClient) -> None:
    tenant_a = await register_owner(stack, client)
    created = await client.post("/companies", json={"name": "A 企业"})
    assert created.status_code == 201
    company_a = uuid.UUID(created.json()["id"])

    # Switch to tenant B by registering (new session cookie)
    _ = await register_owner(stack, client)

    missing = await client.get(f"/companies/{company_a}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "company_not_found"}

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        visible = (
            (await session.execute(select(Company.id).where(Company.tenant_id == tenant_a)))
            .scalars()
            .all()
        )
        assert company_a in visible

    # Tenant B context cannot see tenant A's company rows even without a filter
    tenant_b = stack.tenant_ids[-1]
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        visible = (await session.execute(select(Company.id))).scalars().all()
        assert company_a not in visible

        session.add(
            Company(
                id=uuid.uuid4(),
                tenant_id=tenant_a,
                name="越权写入",
                profile_text="",
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

        result = cast(
            "CursorResult[tuple[()]]",
            await session.execute(
                text("UPDATE companies SET name = 'stolen' WHERE id = :id"),
                {"id": company_a},
            ),
        )
        assert result.rowcount == 0
