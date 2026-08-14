"""Unit coverage for the tenant-facing requirement history assembly."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self, cast, final

import pytest

from relationship_network_api.job_requirement_history_service import (
    RequirementHistorySourceView,
    load_requirement_history,
)
from relationship_network_api.job_service import JobNotFoundError
from relationship_network_api.models import (
    Job,
    JobRequirementDraft,
    JobRequirementDraftSchemaUpgrade,
    JobRequirementInputSource,
    JobRequirementParsingTask,
    JobRequirementVersion,
    TenantAuditEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
JOB_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TASK_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
SNAPSHOT_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
CONFIGURATION_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")
SOURCE_ID = uuid.UUID("77777777-7777-4777-8777-777777777777")
VERSION_ID = uuid.UUID("88888888-8888-4888-8888-888888888888")
DRAFT_ID = uuid.UUID("99999999-9999-4999-8999-999999999999")
UPGRADE_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EVENT_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
PURGED_AT = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


@final
class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None

    def scalars(self) -> Self:
        return self

    def all(self) -> list[object]:
        return self._rows


@final
class _FakeSession:
    """Serves canned rows in the fixed query order of load_requirement_history."""

    def __init__(self, results: list[list[object]]) -> None:
        self._results = deque(results)

    async def execute(self, _statement: object, _params: object = None) -> _FakeResult:
        return _FakeResult(self._results.popleft())


def job_row() -> Job:
    return Job(
        id=JOB_ID,
        tenant_id=TENANT_ID,
        current_requirement_version_id=VERSION_ID,
    )


def task_row() -> JobRequirementParsingTask:
    return JobRequirementParsingTask(
        id=TASK_ID,
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        status="succeeded",
        error_code=None,
        input_snapshot_id=SNAPSHOT_ID,
        configuration_version_id=CONFIGURATION_ID,
        replaces_draft_id=None,
        external_call_count=1,
        structured_invalid_count=0,
        created_by=USER_ID,
        created_at=NOW,
        started_at=NOW,
        completed_at=NOW,
        next_attempt_at=None,
        updated_at=NOW,
    )


def draft_row() -> JobRequirementDraft:
    return JobRequirementDraft(
        id=DRAFT_ID,
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        task_id=TASK_ID,
        input_snapshot_id=SNAPSHOT_ID,
        source_version_id=None,
        requirement_schema_version_id="job-requirement-schema-v1",
        status="confirmed",
        revision=2,
        created_by=USER_ID,
        updated_by=USER_ID,
        status_changed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def version_row() -> JobRequirementVersion:
    return JobRequirementVersion(
        id=VERSION_ID,
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        version_number=1,
        requirement_schema_version_id="job-requirement-schema-v1",
        draft_id=DRAFT_ID,
        source_version_id=None,
        confirmed_by=USER_ID,
        confirmed_at=NOW,
        created_at=NOW,
    )


def upgrade_row() -> JobRequirementDraftSchemaUpgrade:
    return JobRequirementDraftSchemaUpgrade(
        id=UPGRADE_ID,
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        draft_id=DRAFT_ID,
        from_schema_version_id="job-requirement-schema-v1",
        to_schema_version_id="job-requirement-schema-v2",
        converter_version="v1-to-v2@1",
        item_mappings=[{"item_id": "hard-1", "kind": "hard_condition", "lossless": True}],
        lossy_resolutions=[{"item_id": "hard-2", "resolution": None}],
        actor_user_id=USER_ID,
        created_at=NOW,
    )


def source_row() -> JobRequirementInputSource:
    return JobRequirementInputSource(
        id=SOURCE_ID,
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        snapshot_id=SNAPSHOT_ID,
        source_id="job-description",
        source_kind="job-description",
        material_id=None,
        position=0,
        original_sha256="a" * 64,
        sent_sha256="b" * 64,
        unicode_characters=12,
        edited_by=USER_ID,
        edited_at=NOW,
        body_purged_at=PURGED_AT,
    )


def write_denied_event_row() -> TenantAuditEvent:
    return TenantAuditEvent(
        id=EVENT_ID,
        tenant_id=TENANT_ID,
        actor_user_id=USER_ID,
        action="job_requirement.write_denied",
        target_type="job",
        target_id=str(JOB_ID),
        result="failure",
        detail="permission_denied",
        created_at=NOW,
    )


@pytest.mark.anyio
async def test_history_groups_rows_by_business_layer() -> None:
    session = _FakeSession(
        [
            [job_row()],
            [task_row()],
            [draft_row()],
            [version_row()],
            [upgrade_row()],
            [source_row()],
            [write_denied_event_row()],
        ]
    )

    history = await load_requirement_history(
        cast("AsyncSession", cast("object", session)),
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
    )

    assert [task.id for task in history.tasks] == [TASK_ID]
    assert [draft.id for draft in history.drafts] == [DRAFT_ID]
    assert history.drafts[0].requirement_schema_version_id == "job-requirement-schema-v1"
    assert [version.id for version in history.versions] == [VERSION_ID]
    assert history.versions[0].is_current is True
    assert [upgrade.id for upgrade in history.schema_upgrades] == [UPGRADE_ID]
    assert history.schema_upgrades[0].converter_version == "v1-to-v2@1"
    assert [source.snapshot_id for source in history.sources] == [SNAPSHOT_ID]
    assert [event.id for event in history.change_events] == [EVENT_ID]
    event = history.change_events[0]
    assert event.action == "job_requirement.write_denied"
    assert event.target_type == "job"
    assert event.target_id == str(JOB_ID)
    assert event.result == "failure"


@pytest.mark.anyio
async def test_history_sources_expose_purge_metadata_but_never_text_bodies() -> None:
    session = _FakeSession(
        [
            [job_row()],
            [task_row()],
            [draft_row()],
            [version_row()],
            [upgrade_row()],
            [source_row()],
            [write_denied_event_row()],
        ]
    )

    history = await load_requirement_history(
        cast("AsyncSession", cast("object", session)),
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
    )

    source = history.sources[0]
    assert source.body_purged_at == PURGED_AT
    assert source.original_sha256 == "a" * 64
    assert source.sent_sha256 == "b" * 64
    assert source.unicode_characters == 12
    exposed = {field.name for field in fields(RequirementHistorySourceView)}
    assert "body_purged_at" in exposed
    assert exposed.isdisjoint({"original_text", "corrected_text", "sent_text"})


@pytest.mark.anyio
async def test_history_rejects_unknown_jobs() -> None:
    session = _FakeSession([[]])

    with pytest.raises(JobNotFoundError):
        _ = await load_requirement_history(
            cast("AsyncSession", cast("object", session)),
            tenant_id=TENANT_ID,
            job_id=JOB_ID,
        )
