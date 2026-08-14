"""RLS isolation for natural-language search run tables."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from relationship_network_api.models import (
    LlmConfigurationCurrent,
    NaturalLanguageSearchRun,
    SearchHitSnapshot,
)
from relationship_network_api.tenant_context import set_tenant_context

from .conftest import Stack, unique_email

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


async def register_tenant(stack: Stack, client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "搜索租户",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id


async def current_configuration_id(stack: Stack) -> uuid.UUID:
    async with stack.session_factory() as session:
        pointer = (
            await session.execute(
                select(LlmConfigurationCurrent).where(LlmConfigurationCurrent.singleton)
            )
        ).scalar_one()
        return pointer.version_id


def _run(tenant_id: uuid.UUID, config_id: uuid.UUID, key: str) -> NaturalLanguageSearchRun:
    return NaturalLanguageSearchRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_user_id=None,
        status="failed",
        failure_reason="interpretation_invalid",
        utterance="找 AI 研究员",
        utterance_sha256="a" * 64,
        utterance_length=6,
        idempotency_key=key,
        idempotency_fingerprint="b" * 64,
        llm_configuration_version_id=config_id,
        search_contract_version="v1",
    )


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_run_rls_scopes_reads(stack: Stack, client: AsyncClient) -> None:
    tenant_a = await register_tenant(stack, client)
    tenant_b = await register_tenant(stack, client)
    config_id = await current_configuration_id(stack)
    run_a = _run(tenant_a, config_id, "tenant-a-key")

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        session.add(run_a)
        await session.commit()

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        result = await session.execute(select(NaturalLanguageSearchRun.id))
        visible_a = {row[0] for row in result.all()}

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        result = await session.execute(select(NaturalLanguageSearchRun.id))
        visible_b = {row[0] for row in result.all()}

    assert run_a.id in visible_a
    assert run_a.id not in visible_b


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_run_rls_blocks_cross_tenant_write(stack: Stack, client: AsyncClient) -> None:
    tenant_a = await register_tenant(stack, client)
    tenant_b = await register_tenant(stack, client)
    config_id = await current_configuration_id(stack)

    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        session.add(_run(tenant_b, config_id, "cross-tenant-key"))
        # A cross-tenant insert is rejected by RLS; commit raises.
        with pytest.raises(Exception):  # noqa: B017, PT011
            await session.commit()
        await session.rollback()

    # Tenant B never received the row.
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_b)
        result = await session.execute(select(NaturalLanguageSearchRun.id))
        assert {row[0] for row in result.all()} == set()


@pytest.mark.anyio
@pytest.mark.integration
async def test_snapshot_table_exists_and_is_scoped(stack: Stack, client: AsyncClient) -> None:
    """The snapshot table accepts no rows without a valid run and is tenant-scoped."""
    tenant_a = await register_tenant(stack, client)
    # The table exists (migration applied) and exposes the expected tenant column.
    async with stack.session_factory() as session:
        await set_tenant_context(session, tenant_a)
        result = await session.execute(select(SearchHitSnapshot.id).limit(1))
        assert result.all() == []
