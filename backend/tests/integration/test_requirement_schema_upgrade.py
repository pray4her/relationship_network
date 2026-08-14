# ruff: noqa: RUF001

"""Integration coverage for explicit draft schema upgrades and history facts.

Tests run against a throwaway scratch database created once per module (the
append-only triggers on versions and input sources intentionally forbid row
deletion, so per-test cleanup is impossible by design; the scratch database
is dropped wholesale at module teardown).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from relationship_network_api import job_requirement_draft_service as draft_service
from relationship_network_api import job_requirement_version_service as version_service
from relationship_network_api import tenant_audit_service
from relationship_network_api.config import load_database_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.job_requirement_history_service import load_requirement_history
from relationship_network_api.job_requirement_schema_upgrade import CONVERTER_V1_TO_V2
from relationship_network_api.job_requirement_validation import (
    build_editable_requirement_document,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    Company,
    Job,
    JobRequirementDraft,
    JobRequirementDraftSchemaUpgrade,
    JobRequirementInputSnapshot,
    JobRequirementInputSource,
    JobRequirementVersion,
    Tenant,
    TenantAuditEvent,
    User,
)
from relationship_network_api.tenant_context import set_tenant_context

SCHEMA_V1 = manifest.JOB_REQUIREMENT_SCHEMA_V1.id
SCHEMA_V2 = manifest.JOB_REQUIREMENT_SCHEMA_V2.id
SCRATCH_DB = f"rn_itest_schema_upgrade_{os.getpid()}"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Seed:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    draft_id: uuid.UUID


def _admin_url() -> str:
    return str(load_database_settings().database_url).rsplit("/", 1)[0]


async def _create_scratch_db() -> None:
    engine = create_async_engine(f"{_admin_url()}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            _ = await connection.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB} WITH (FORCE)"))
            _ = await connection.execute(text(f"CREATE DATABASE {SCRATCH_DB}"))
    finally:
        await engine.dispose()


def _migrate_scratch_db(scratch_url: str) -> None:
    environment = {**os.environ, "RN_DATABASE_URL": scratch_url}
    _ = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
    )


async def _drop_scratch_db() -> None:
    engine = create_async_engine(f"{_admin_url()}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            _ = await connection.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB} WITH (FORCE)"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def scratch_database() -> Iterator[str]:
    base_url = _admin_url()
    scratch_url = f"{base_url}/{SCRATCH_DB}"
    asyncio.run(_create_scratch_db())
    _migrate_scratch_db(scratch_url)
    previous = os.environ.get("RN_DATABASE_URL")
    os.environ["RN_DATABASE_URL"] = scratch_url
    try:
        yield scratch_url
    finally:
        if previous is None:
            del os.environ["RN_DATABASE_URL"]
        else:
            os.environ["RN_DATABASE_URL"] = previous
        asyncio.run(_drop_scratch_db())


@pytest.fixture
async def engine(scratch_database: str) -> AsyncIterator[AsyncEngine]:
    _ = scratch_database
    del scratch_database
    settings = load_database_settings()
    engine = create_engine_from_settings(settings)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def target_v2_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_target(_session: object) -> str:
        return SCHEMA_V2

    monkeypatch.setattr(draft_service, "_current_prompt_compatible_schema_id", fake_target)


def evidence(source_id: str, text_body: str, quote: str) -> dict[str, object]:
    start = text_body.index(quote)
    return {
        "source_id": source_id,
        "start_offset": start,
        "end_offset": start + len(quote),
        "quote": quote,
    }


def model_result(*, lossy: bool) -> dict[str, object]:
    description = "需要海外华人，研究人工智能。"
    hard_condition = (
        {
            "field": "chinese_identity",
            "operator": "eq",
            "value": "未知身份",
            "description": "需要未知身份",
            "evidence": [evidence("job-description", description, "海外华人")],
        }
        if lossy
        else {
            "field": "h_index",
            "operator": "gte",
            "value": 30,
            "description": "H 指数至少 30",
            "evidence": [evidence("job-description", description, "海外华人")],
        }
    )
    return {
        "hard_conditions": [hard_condition],
        "preference_conditions": [],
        "research_topic_query": "人工智能",
        "unsupported_conditions": [],
        "source_conflicts": [],
    }


async def seed_tenant_with_draft(
    session: AsyncSession,
    *,
    schema_id: str = SCHEMA_V1,
    lossy: bool = False,
) -> Seed:
    seed = Seed(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    document = build_editable_requirement_document(
        model_result(lossy=lossy),
        draft_id=seed.draft_id,
    )
    session.add(
        Tenant(
            id=seed.tenant_id,
            name="升级租户",
            slug=f"schema-upgrade-{seed.tenant_id.hex}",
        )
    )
    session.add(
        User(
            id=seed.user_id,
            email=f"schema-upgrade-{seed.user_id.hex}@example.com",
            display_name="升级成员",
            password_hash="not-a-real-hash",
        )
    )
    await session.commit()
    await set_tenant_context(session, seed.tenant_id)
    session.add(Company(id=uuid.uuid4(), tenant_id=seed.tenant_id, name="升级企业"))
    await session.flush()
    company = (
        await session.execute(select(Company).where(Company.tenant_id == seed.tenant_id))
    ).scalar_one()
    session.add(
        Job(
            id=seed.job_id,
            tenant_id=seed.tenant_id,
            company_id=company.id,
            title="研究人才负责人",
            description="需要海外华人",
        )
    )
    session.add(
        JobRequirementDraft(
            id=seed.draft_id,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            requirement_schema_version_id=schema_id,
            result_json=document,
            status="editable",
            revision=1,
            created_by=seed.user_id,
            updated_by=seed.user_id,
        )
    )
    await session.commit()
    return seed


async def latest_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: str,
) -> TenantAuditEvent | None:
    return (
        (
            await session.execute(
                select(TenantAuditEvent)
                .where(
                    TenantAuditEvent.tenant_id == tenant_id,
                    TenantAuditEvent.action == action,
                )
                .order_by(TenantAuditEvent.created_at.desc())
            )
        )
        .scalars()
        .first()
    )


@pytest.mark.anyio
@pytest.mark.integration
@pytest.mark.usefixtures("target_v2_schema")
async def test_upgrade_success_persists_record_and_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session)
        await set_tenant_context(session, seed.tenant_id)
        result = await draft_service.upgrade_draft_schema(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=1,
        )

        assert result.draft.requirement_schema_version_id == SCHEMA_V2
        assert result.draft.revision == 2
        assert result.draft.pending_upgrade_items == []
        assert result.upgrade.from_schema_version_id == SCHEMA_V1
        assert result.upgrade.to_schema_version_id == SCHEMA_V2
        assert result.upgrade.converter_version == CONVERTER_V1_TO_V2
        assert result.upgrade.actor_user_id == seed.user_id
        assert result.upgrade.lossy_resolutions == []
        assert [mapping["lossless"] for mapping in result.upgrade.item_mappings] == [True]

        await set_tenant_context(session, seed.tenant_id)
        persisted = (
            await session.execute(
                select(JobRequirementDraftSchemaUpgrade).where(
                    JobRequirementDraftSchemaUpgrade.tenant_id == seed.tenant_id,
                    JobRequirementDraftSchemaUpgrade.draft_id == seed.draft_id,
                )
            )
        ).scalar_one()
        assert persisted.converter_version == CONVERTER_V1_TO_V2
        hard_conditions = persisted.pre_upgrade_json["hard_conditions"]
        assert isinstance(hard_conditions, list)
        assert [item["field"] for item in hard_conditions] == ["h_index"]

        audit = await latest_audit(
            session,
            tenant_id=seed.tenant_id,
            action=draft_service.ACTION_SCHEMA_UPGRADE,
        )
        assert audit is not None
        assert audit.result == tenant_audit_service.AUDIT_RESULT_SUCCESS
        assert audit.target_id == str(seed.draft_id)


@pytest.mark.anyio
@pytest.mark.integration
@pytest.mark.usefixtures("target_v2_schema")
async def test_upgrade_unavailable_when_draft_already_on_target_schema(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session, schema_id=SCHEMA_V2)
        await set_tenant_context(session, seed.tenant_id)
        with pytest.raises(draft_service.RequirementDraftError) as captured:
            _ = await draft_service.upgrade_draft_schema(
                session,
                tenant_id=seed.tenant_id,
                job_id=seed.job_id,
                draft_id=seed.draft_id,
                actor_user_id=seed.user_id,
                expected_revision=1,
            )
        assert captured.value.code == draft_service.SCHEMA_UPGRADE_UNAVAILABLE

        await set_tenant_context(session, seed.tenant_id)
        audit = await latest_audit(
            session,
            tenant_id=seed.tenant_id,
            action=draft_service.ACTION_SCHEMA_UPGRADE,
        )
        assert audit is not None
        assert audit.result == tenant_audit_service.AUDIT_RESULT_FAILURE
        assert audit.detail == draft_service.SCHEMA_UPGRADE_UNAVAILABLE


@pytest.mark.anyio
@pytest.mark.integration
@pytest.mark.usefixtures("target_v2_schema")
async def test_lossy_upgrade_blocks_confirm_until_drop_resolution(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session, lossy=True)
        await set_tenant_context(session, seed.tenant_id)
        upgraded = await draft_service.upgrade_draft_schema(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=1,
        )
        pending = upgraded.draft.pending_upgrade_items
        assert len(pending) == 1
        assert pending[0]["kind"] == "hard_condition"
        assert upgraded.draft.result["hard_conditions"] == []

        await set_tenant_context(session, seed.tenant_id)
        with pytest.raises(version_service.RequirementVersionError) as captured:
            _ = await version_service.confirm_draft(
                session,
                tenant_id=seed.tenant_id,
                job_id=seed.job_id,
                draft_id=seed.draft_id,
                actor_user_id=seed.user_id,
                expected_revision=2,
            )
        assert captured.value.code == draft_service.SCHEMA_UPGRADE_LOSSY_UNRESOLVED

        await set_tenant_context(session, seed.tenant_id)
        resolved = await draft_service.resolve_schema_upgrade_lossy_items(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            upgrade_id=upgraded.upgrade.id,
            actor_user_id=seed.user_id,
            expected_revision=2,
            resolutions=[
                draft_service.LossyResolutionSubmission(
                    item_id=cast("str", pending[0]["item_id"]),
                    resolution=draft_service.RESOLUTION_DROP,
                )
            ],
        )
        assert resolved.pending_upgrade_items == []
        removed_facts = resolved.result["removed_facts"]
        assert isinstance(removed_facts, list)
        assert [item["kind"] for item in removed_facts] == ["hard_condition"]

        await set_tenant_context(session, seed.tenant_id)
        confirmed = await version_service.confirm_draft(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=3,
        )
        assert confirmed.version.version_number == 1
        assert confirmed.version.is_current is True

        await set_tenant_context(session, seed.tenant_id)
        version = (
            await session.execute(
                select(JobRequirementVersion).where(
                    JobRequirementVersion.tenant_id == seed.tenant_id,
                    JobRequirementVersion.draft_id == seed.draft_id,
                )
            )
        ).scalar_one()
        job = (
            await session.execute(
                select(Job).where(Job.id == seed.job_id, Job.tenant_id == seed.tenant_id)
            )
        ).scalar_one()
        assert job.current_requirement_version_id == version.id


@pytest.mark.anyio
@pytest.mark.integration
@pytest.mark.usefixtures("target_v2_schema")
async def test_downgrade_resolution_moves_lossy_item_to_unsupported_conditions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session, lossy=True)
        await set_tenant_context(session, seed.tenant_id)
        upgraded = await draft_service.upgrade_draft_schema(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=1,
        )
        pending = upgraded.draft.pending_upgrade_items

        await set_tenant_context(session, seed.tenant_id)
        resolved = await draft_service.resolve_schema_upgrade_lossy_items(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            upgrade_id=upgraded.upgrade.id,
            actor_user_id=seed.user_id,
            expected_revision=2,
            resolutions=[
                draft_service.LossyResolutionSubmission(
                    item_id=cast("str", pending[0]["item_id"]),
                    resolution=draft_service.RESOLUTION_DOWNGRADE,
                )
            ],
        )
        assert resolved.pending_upgrade_items == []
        unsupported = cast("list[dict[str, object]]", resolved.result["unsupported_conditions"])
        assert len(unsupported) == 1
        assert unsupported[0]["origin"] == "user_added"
        assert unsupported[0]["description"] == "需要未知身份"

        await set_tenant_context(session, seed.tenant_id)
        confirmed = await version_service.confirm_draft(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=3,
        )
        assert confirmed.version.version_number == 1


@pytest.mark.anyio
@pytest.mark.integration
@pytest.mark.usefixtures("target_v2_schema")
async def test_resolve_rejects_unknown_resolved_and_missing_records(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session, lossy=True)
        await set_tenant_context(session, seed.tenant_id)
        upgraded = await draft_service.upgrade_draft_schema(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
            draft_id=seed.draft_id,
            actor_user_id=seed.user_id,
            expected_revision=1,
        )
        pending = upgraded.draft.pending_upgrade_items

        async def resolve(
            *,
            upgrade_id: uuid.UUID,
            expected_revision: int,
            item_id: str,
        ) -> draft_service.RequirementDraftMutationView:
            await set_tenant_context(session, seed.tenant_id)
            return await draft_service.resolve_schema_upgrade_lossy_items(
                session,
                tenant_id=seed.tenant_id,
                job_id=seed.job_id,
                draft_id=seed.draft_id,
                upgrade_id=upgrade_id,
                actor_user_id=seed.user_id,
                expected_revision=expected_revision,
                resolutions=[
                    draft_service.LossyResolutionSubmission(
                        item_id=item_id,
                        resolution=draft_service.RESOLUTION_DROP,
                    )
                ],
            )

        with pytest.raises(draft_service.RequirementDraftError) as unknown_item:
            _ = await resolve(
                upgrade_id=upgraded.upgrade.id,
                expected_revision=2,
                item_id=str(uuid.uuid4()),
            )
        assert unknown_item.value.code == draft_service.SCHEMA_UPGRADE_RESOLUTION_INVALID

        with pytest.raises(draft_service.RequirementDraftError) as missing_upgrade:
            _ = await resolve(
                upgrade_id=uuid.uuid4(),
                expected_revision=2,
                item_id=cast("str", pending[0]["item_id"]),
            )
        assert missing_upgrade.value.code == draft_service.SCHEMA_UPGRADE_NOT_FOUND

        resolved = await resolve(
            upgrade_id=upgraded.upgrade.id,
            expected_revision=2,
            item_id=cast("str", pending[0]["item_id"]),
        )
        assert resolved.pending_upgrade_items == []

        with pytest.raises(draft_service.RequirementDraftError) as already_resolved:
            _ = await resolve(
                upgrade_id=upgraded.upgrade.id,
                expected_revision=3,
                item_id=cast("str", pending[0]["item_id"]),
            )
        assert already_resolved.value.code == draft_service.SCHEMA_UPGRADE_RESOLUTION_INVALID


@pytest.mark.anyio
@pytest.mark.integration
async def test_history_scopes_write_denied_events_and_exposes_source_metadata(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        seed = await seed_tenant_with_draft(session, schema_id=SCHEMA_V2)
        snapshot_id = uuid.uuid4()
        other_job_id = uuid.uuid4()
        await set_tenant_context(session, seed.tenant_id)
        configuration_id = (
            await session.execute(
                text("SELECT version_id FROM llm_configuration_current WHERE singleton")
            )
        ).scalar_one()
        session.add(
            JobRequirementInputSnapshot(
                id=snapshot_id,
                tenant_id=seed.tenant_id,
                job_id=seed.job_id,
                configuration_version_id=configuration_id,
                total_characters=4,
                content_sha256="c" * 64,
            )
        )
        session.add(
            JobRequirementInputSource(
                id=uuid.uuid4(),
                tenant_id=seed.tenant_id,
                job_id=seed.job_id,
                snapshot_id=snapshot_id,
                source_id="job-description",
                source_kind="job-description",
                position=0,
                original_text="原始正文",
                corrected_text="修正正文",
                sent_text="发送正文",
                original_sha256="a" * 64,
                sent_sha256="b" * 64,
                unicode_characters=4,
            )
        )
        for target_job_id in (seed.job_id, other_job_id):
            tenant_audit_service.record_event(
                session,
                tenant_id=seed.tenant_id,
                actor_user_id=seed.user_id,
                action="job_requirement.write_denied",
                target_type="job",
                target_id=str(target_job_id),
                result=tenant_audit_service.AUDIT_RESULT_FAILURE,
                detail="permission_denied",
            )
        await session.commit()

        await set_tenant_context(session, seed.tenant_id)
        history = await load_requirement_history(
            session,
            tenant_id=seed.tenant_id,
            job_id=seed.job_id,
        )

        assert history.tasks == []
        assert [draft.id for draft in history.drafts] == [seed.draft_id]
        denied = [
            event
            for event in history.change_events
            if event.action == "job_requirement.write_denied"
        ]
        assert [event.target_id for event in denied] == [str(seed.job_id)]
        assert len(history.sources) == 1
        source = history.sources[0]
        assert source.snapshot_id == snapshot_id
        assert source.body_purged_at is None
        assert source.original_sha256 == "a" * 64
        assert source.unicode_characters == 4
