"""Integration coverage for the tenant requirement-generation boundary."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from relationship_network_api.models import TenantAuditEvent, UsageLedgerEntry
from relationship_network_api.tenant_context import set_tenant_context

from .conftest import Stack, unique_email

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


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
            "display_name": "需求生成租户主",
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
async def test_v1_configuration_is_not_ready_and_rejection_is_audited(
    stack: Stack,
    client: AsyncClient,
) -> None:
    tenant_id = await register_owner(stack, client)
    company = await client.post("/companies", json={"name": "需求企业"})
    assert company.status_code == 201
    job = await client.post(
        "/jobs",
        json={
            "company_id": company.json()["id"],
            "title": "研究人才负责人",
            "description": "需要海外华人，研究人工智能。",  # noqa: RUF001
        },
    )
    assert job.status_code == 201
    job_id = job.json()["id"]
    material = await client.post(
        f"/jobs/{job_id}/materials",
        files={"file": ("补充说明.txt", "H 指数至少 30".encode(), "text/plain")},
    )
    assert material.status_code == 201

    workspace = await client.get(f"/jobs/{job_id}/requirement-generation")
    assert workspace.status_code == 200
    body = workspace.json()
    assert body["configuration_ready"] is False
    assert body["input_character_limit"] == 100_000
    assert [source["source_id"] for source in body["sources"]] == [
        "job-description",
        f"job-material:{material.json()['id']}",
    ]

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        before_usage = (
            await session.execute(
                select(func.count())
                .select_from(UsageLedgerEntry)
                .where(UsageLedgerEntry.tenant_id == tenant_id)
            )
        ).scalar_one()

    rejected = await client.post(
        f"/jobs/{job_id}/requirement-parsing-tasks",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "sources": [{"source_id": "job-description", "corrected_text": "需要海外华人"}],
        },
    )
    assert rejected.status_code == 409
    assert rejected.json() == {"detail": "requirement_configuration_not_ready"}

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_id)
        audit = (
            (
                await session.execute(
                    select(TenantAuditEvent)
                    .where(
                        TenantAuditEvent.tenant_id == tenant_id,
                        TenantAuditEvent.action == "job_requirement_parsing.create",
                    )
                    .order_by(TenantAuditEvent.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        after_usage = (
            await session.execute(
                select(func.count())
                .select_from(UsageLedgerEntry)
                .where(UsageLedgerEntry.tenant_id == tenant_id)
            )
        ).scalar_one()

    assert audit is not None
    assert audit.result == "failure"
    assert audit.detail == "requirement_configuration_not_ready"
    assert after_usage == before_usage
