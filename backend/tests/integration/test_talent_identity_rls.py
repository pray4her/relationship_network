"""Integration tests for the shared local-talent master and its RLS posture."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relationship_network_api.config import load_app_settings
from relationship_network_api.db import (
    TALENT_SYNC_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.fake_search_base import (
    DEFAULT_SERVICE_API_KEY,
    SEEDED_PERSON_ID,
    state,
)
from relationship_network_api.models import LocalTalent, TalentExternalId
from relationship_network_api.search_base import SearchBaseAdapter, SearchBaseClientConfig
from relationship_network_api.talent_identity_service import sync_person

from .conftest import Stack, unique_email


@pytest.fixture
async def client(stack: Stack) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=stack.transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def sync_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = load_app_settings()
    engine = create_engine_from_settings(settings, database_role=TALENT_SYNC_DATABASE_ROLE)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def make_adapter(base_url: str) -> SearchBaseAdapter:
    return SearchBaseAdapter(
        SearchBaseClientConfig(api_key=DEFAULT_SERVICE_API_KEY, base_url=base_url)
    )


async def register_user(stack: Stack, client: AsyncClient) -> uuid.UUID:
    """Register a tenant through the API; returns the tenant id."""
    email = unique_email()
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "integration-secret-1",
            "display_name": "人才查看者",
            "tenant_name": None,
        },
    )
    assert response.status_code == 201
    tenant_id = uuid.UUID(cast("dict[str, dict[str, str]]", response.json())["tenant"]["id"])
    stack.emails.append(email)
    stack.tenant_ids.append(tenant_id)
    return tenant_id


def _intruder_talent() -> LocalTalent:
    return LocalTalent(
        id=uuid.uuid4(),
        canonical_person_id="cp-intruder",
        display_name="X",
        current_affiliation="Y",
        country="CN",
        chinese_identity="国内华人",
        h_index=0,
        total_citations=0,
        data_version="dv-seed-001",
        availability="available",
    )


@pytest.mark.anyio
@pytest.mark.integration
async def test_sync_then_read_talent_via_api(
    stack: Stack,
    client: AsyncClient,
    fake_search_base_base_url: str,
    sync_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _ = await register_user(stack, client)
    adapter = make_adapter(fake_search_base_base_url)

    async with sync_session_factory() as session:
        view = await sync_person(session, adapter, SEEDED_PERSON_ID)

    assert view is not None
    assert view.availability == "available"

    response = await client.get(f"/talents/{view.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Wei Zhang"
    assert body["availability"] == "available"
    assert body["data_version"] == "dv-seed-001"
    assert body["historical_source_ids"] == ["src-openalex-001", "src-orcid-001"]


@pytest.mark.anyio
@pytest.mark.integration
async def test_global_talent_is_read_only_for_app_role(
    stack: Stack,
    client: AsyncClient,
    fake_search_base_base_url: str,
    sync_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _ = await register_user(stack, client)
    adapter = make_adapter(fake_search_base_base_url)

    async with sync_session_factory() as session:
        view = await sync_person(session, adapter, SEEDED_PERSON_ID)
    assert view is not None
    talent_id = view.id

    # App role reads the shared talent.
    async with stack.session_factory() as session:
        result = await session.execute(select(LocalTalent.id).where(LocalTalent.id == talent_id))
        assert result.scalar_one() == talent_id

    # App role cannot insert.
    async with stack.session_factory() as session:
        session.add(_intruder_talent())
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()

    # App role cannot update.
    async with stack.session_factory() as session:
        with pytest.raises(DBAPIError):
            _ = await session.execute(
                text("UPDATE local_talents SET display_name = 'hacked' WHERE id = :id"),
                {"id": talent_id},
            )
        await session.rollback()

    # App role cannot delete.
    async with stack.session_factory() as session:
        with pytest.raises(DBAPIError):
            _ = await session.execute(
                text("DELETE FROM local_talents WHERE id = :id"),
                {"id": talent_id},
            )
        await session.rollback()


@pytest.mark.anyio
@pytest.mark.integration
async def test_concurrent_sync_serializes_to_one_talent(
    stack: Stack,
    client: AsyncClient,
    fake_search_base_base_url: str,
    sync_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _ = await register_user(stack, client)
    adapter = make_adapter(fake_search_base_base_url)

    async def do_sync() -> uuid.UUID:
        async with sync_session_factory() as session:
            view = await sync_person(session, adapter, SEEDED_PERSON_ID)
            assert view is not None
            return view.id

    talent_ids = await asyncio.gather(*(do_sync() for _ in range(5)))
    assert len(set(talent_ids)) == 1

    async with sync_session_factory() as session:
        mappings = (
            await session.execute(
                select(TalentExternalId.external_id).where(
                    TalentExternalId.external_id == SEEDED_PERSON_ID
                )
            )
        ).all()
    assert len(mappings) == 1


@pytest.mark.anyio
@pytest.mark.integration
async def test_availability_loop_through_absence(
    stack: Stack,
    client: AsyncClient,
    fake_search_base_base_url: str,
    sync_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _ = await register_user(stack, client)
    adapter = make_adapter(fake_search_base_base_url)

    async with sync_session_factory() as session:
        available = await sync_person(session, adapter, SEEDED_PERSON_ID)
    assert available is not None
    assert available.availability == "available"
    original_name = available.display_name

    state.absent_person_ids.add(SEEDED_PERSON_ID)
    try:
        async with sync_session_factory() as session:
            unavailable = await sync_person(session, adapter, SEEDED_PERSON_ID)
        assert unavailable is not None
        assert unavailable.availability == "temporarily_unavailable"
        assert unavailable.display_name == original_name
    finally:
        state.absent_person_ids.discard(SEEDED_PERSON_ID)

    async with sync_session_factory() as session:
        recovered = await sync_person(session, adapter, SEEDED_PERSON_ID)
    assert recovered is not None
    assert recovered.availability == "available"
