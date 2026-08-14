"""Route-level tests for the requirement generation workspace."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from relationship_network_api import (
    job_requirement_draft_service,
    job_requirement_history_service,
    job_requirement_service,
    job_requirement_version_service,
    tenant_audit_service,
    usage_service,
)
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import TenantContext, get_db_session, get_tenant_context
from relationship_network_api.job_service import JOB_NOT_FOUND_DETAIL, JobNotFoundError
from relationship_network_api.main import create_app
from relationship_network_api.routers import job_requirements
from relationship_network_api.tenant_audit_service import TenantAuditEventView

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from _pytest.monkeypatch import MonkeyPatch
    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
JOB_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TASK_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
SNAPSHOT_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
CONFIGURATION_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")
DRAFT_ID = uuid.UUID("99999999-9999-4999-8999-999999999999")
UPGRADE_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EVENT_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
RESOLUTION_ITEM_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "88888888-8888-4888-8888-888888888888"


def make_context(permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=uuid.UUID("77777777-7777-4777-8777-777777777777"),
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme",
        role="owner",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(id=USER_ID, email="owner@example.com", display_name="Owner"),
            membership=membership,
            expires_at=NOW + timedelta(days=1),
            renewed=False,
        ),
        membership=membership,
        permissions=permissions,
    )


def make_client(permissions: frozenset[str], *, writable: bool = True) -> TestClient:
    context = make_context(permissions)
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    async def override_context() -> TenantContext:
        return context

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_tenant_context] = override_context
    if "jobs:read" in permissions:
        app.dependency_overrides[job_requirements.require_requirement_jobs_read] = override_context

    async def override_manage() -> TenantContext:
        if "jobs:manage" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="permission_denied",
            )
        if not writable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="subscription_read_only",
            )
        return context

    app.dependency_overrides[job_requirements.require_requirement_jobs_manage_audited] = (
        override_manage
    )
    return TestClient(app)


def task_view() -> job_requirement_service.RequirementTaskView:
    return job_requirement_service.RequirementTaskView(
        id=TASK_ID,
        status="queued",
        error_code=None,
        input_snapshot_id=SNAPSHOT_ID,
        configuration_version_id=CONFIGURATION_ID,
        replaces_draft_id=None,
        external_call_count=0,
        structured_invalid_count=0,
        created_by=USER_ID,
        created_at=NOW,
        started_at=None,
        completed_at=None,
        next_attempt_at=None,
        updated_at=NOW,
    )


def draft_view(
    *,
    revision: int = 2,
) -> job_requirement_draft_service.RequirementDraftMutationView:
    return job_requirement_draft_service.RequirementDraftMutationView(
        id=DRAFT_ID,
        task_id=TASK_ID,
        input_snapshot_id=SNAPSHOT_ID,
        source_version_id=None,
        requirement_schema_version_id="job-requirement-schema-v2",
        status="editable",
        revision=revision,
        result={
            "hard_conditions": [],
            "preference_conditions": [],
            "research_topic_query": {
                "value": "人工智能",
                "model_value": "人工智能",
                "last_modified_by": None,
                "last_modified_at": None,
            },
            "unsupported_conditions": [],
            "source_conflicts": [],
            "removed_facts": [],
        },
        updated_by=USER_ID,
        status_changed_at=NOW,
        read_only_reason=None,
        field_catalog={"h_index": ["gte", "lte", "between"]},
        chinese_identity_values=["国内华人", "海外华人", "外国人"],
        created_at=NOW,
        updated_at=NOW,
    )


def test_workspace_requires_jobs_read(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_requirement_service, "load_workspace", should_not_run)
    response = make_client(frozenset()).get(f"/jobs/{JOB_ID}/requirement-generation")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "permission_denied"}


def test_workspace_returns_v2_readiness_and_deterministic_sources(monkeypatch: MonkeyPatch) -> None:
    async def fake_workspace(*_args: object, **_kwargs: object) -> object:
        return job_requirement_service.RequirementWorkspaceView(
            configuration_ready=True,
            input_character_limit=100_000,
            sources=[
                job_requirement_service.RequirementSourceView(
                    source_id="job-description",
                    source_kind="job-description",
                    material_id=None,
                    label="职位描述",
                    original_text="负责人才检索",
                    scan_status="not_applicable",
                    created_at=None,
                )
            ],
            task=task_view(),
            draft=None,
            current_version=None,
            versions=[],
            legacy_requirement_exempt=False,
            matching_blocked=False,
        )

    monkeypatch.setattr(job_requirement_service, "load_workspace", fake_workspace)
    response = make_client(frozenset({"jobs:read"})).get(f"/jobs/{JOB_ID}/requirement-generation")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["configuration_ready"] is True
    assert body["input_character_limit"] == 100_000
    assert body["sources"][0]["source_id"] == "job-description"
    assert body["task"]["id"] == str(TASK_ID)


def test_create_task_requires_manage_and_writable_tenant(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_requirement_service, "create_parsing_task", should_not_run)
    body = {
        "idempotency_key": IDEMPOTENCY_KEY,
        "sources": [{"source_id": "job-description", "corrected_text": "描述"}],
    }

    forbidden = make_client(frozenset({"jobs:read"})).post(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks", json=body
    )
    read_only = make_client(frozenset({"jobs:manage"}), writable=False).post(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks", json=body
    )

    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden.json() == {"detail": "permission_denied"}
    assert read_only.status_code == status.HTTP_403_FORBIDDEN
    assert read_only.json() == {"detail": "subscription_read_only"}


def test_create_task_returns_202_and_server_submission_shape(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return task_view()

    monkeypatch.setattr(job_requirement_service, "create_parsing_task", fake_create)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks",
        json={
            "idempotency_key": IDEMPOTENCY_KEY,
            "sources": [{"source_id": "job-description", "corrected_text": "修正描述"}],
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["status"] == "queued"
    assert captured["tenant_id"] == TENANT_ID
    assert captured["job_id"] == JOB_ID
    assert captured["idempotency_key"] == IDEMPOTENCY_KEY
    submissions = cast(
        "list[job_requirement_service.RequirementSourceSubmission]", captured["submissions"]
    )
    assert submissions == [
        job_requirement_service.RequirementSourceSubmission(
            source_id="job-description", corrected_text="修正描述"
        )
    ]


def test_cancel_task_returns_latest_persisted_state(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_cancel(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return replace(task_view(), status="cancelled", completed_at=NOW)

    monkeypatch.setattr(job_requirement_service, "cancel_parsing_task", fake_cancel)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks/{TASK_ID}/cancel"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "cancelled"
    assert captured == {
        "tenant_id": TENANT_ID,
        "job_id": JOB_ID,
        "task_id": TASK_ID,
        "actor_user_id": USER_ID,
    }


def test_update_draft_uses_manage_gate_and_returns_normalized_snapshot(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return draft_view()

    monkeypatch.setattr(job_requirement_draft_service, "update_requirement_draft", fake_update)
    body = {
        "expected_revision": 1,
        "result": {
            "hard_conditions": [],
            "preference_conditions": [],
            "research_topic_query": " 人工智能 ",
            "unsupported_conditions": [],
            "source_conflicts": [],
        },
    }
    response = make_client(frozenset({"jobs:manage"})).put(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}",
        json=body,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["revision"] == 2
    assert response.json()["field_catalog"]["h_index"] == ["gte", "lte", "between"]
    assert captured["expected_revision"] == 1
    assert captured["actor_user_id"] == USER_ID
    assert cast("dict[str, object]", captured["submitted"])["research_topic_query"] == (
        " 人工智能 "
    )


def test_revision_conflict_returns_the_latest_complete_draft(monkeypatch: MonkeyPatch) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_draft_service.RequirementDraftError(
            job_requirement_draft_service.DRAFT_REVISION_CONFLICT,
            latest=draft_view(revision=4),
        )

    monkeypatch.setattr(job_requirement_draft_service, "update_requirement_draft", reject)
    response = make_client(frozenset({"jobs:manage"})).put(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}",
        json={
            "expected_revision": 2,
            "result": {
                "hard_conditions": [],
                "preference_conditions": [],
                "research_topic_query": "人工智能",
                "unsupported_conditions": [],
                "source_conflicts": [],
            },
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == job_requirement_draft_service.DRAFT_REVISION_CONFLICT
    assert response.json()["draft"]["revision"] == 4


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        (job_requirement_draft_service.DRAFT_INVALID, status.HTTP_422_UNPROCESSABLE_CONTENT),
        (job_requirement_draft_service.DRAFT_LOCKED, status.HTTP_409_CONFLICT),
        (job_requirement_draft_service.DRAFT_NOT_EDITABLE, status.HTTP_409_CONFLICT),
        (job_requirement_draft_service.DRAFT_NOT_FOUND, status.HTTP_404_NOT_FOUND),
    ],
)
def test_update_draft_maps_stable_business_errors(
    monkeypatch: MonkeyPatch,
    code: str,
    expected_status: int,
) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_draft_service.RequirementDraftError(code)

    monkeypatch.setattr(job_requirement_draft_service, "update_requirement_draft", reject)
    response = make_client(frozenset({"jobs:manage"})).put(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}",
        json={
            "expected_revision": 1,
            "result": {
                "hard_conditions": [],
                "preference_conditions": [],
                "research_topic_query": "人工智能",
                "unsupported_conditions": [],
                "source_conflicts": [],
            },
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": code}


def test_abandon_draft_requires_manage_and_writable_tenant(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        message = "service should not run"
        raise AssertionError(message)

    monkeypatch.setattr(
        job_requirement_draft_service,
        "abandon_requirement_draft",
        should_not_run,
    )
    path = f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/abandon"
    forbidden = make_client(frozenset({"jobs:read"})).post(
        path,
        json={"expected_revision": 1},
    )
    read_only = make_client(frozenset({"jobs:manage"}), writable=False).post(
        path,
        json={"expected_revision": 1},
    )

    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden.json() == {"detail": "permission_denied"}
    assert read_only.status_code == status.HTTP_403_FORBIDDEN
    assert read_only.json() == {"detail": "subscription_read_only"}


def test_event_stream_replays_after_cursor_and_closes_on_terminal_event(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_get_task(*_args: object, **_kwargs: object) -> object:
        return task_view()

    async def fake_list_events(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return [
            job_requirement_service.RequirementTaskEventView(
                sequence_number=4,
                task_id=TASK_ID,
                status="cancelled",
                error_code=None,
                retryable=False,
                next_attempt_at=None,
                created_at=NOW,
            )
        ]

    monkeypatch.setattr(job_requirement_service, "get_task", fake_get_task)
    monkeypatch.setattr(job_requirement_service, "list_task_events", fake_list_events)
    response = make_client(frozenset({"jobs:read"})).get(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks/{TASK_ID}/events",
        headers={"Last-Event-ID": "3"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert "id: 4\nevent: cancelled\n" in response.text
    assert captured["after_sequence"] == 3


def test_event_stream_rejects_malformed_last_event_id() -> None:
    response = make_client(frozenset({"jobs:read"})).get(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks/{TASK_ID}/events",
        headers={"Last-Event-ID": "not-an-integer"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": job_requirement_service.INVALID_LAST_EVENT_ID}


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        (job_requirement_service.SOURCE_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (job_requirement_service.EMPTY_MATERIAL_CORRECTION, status.HTTP_422_UNPROCESSABLE_CONTENT),
        (job_requirement_service.INPUT_TOO_LARGE, status.HTTP_413_CONTENT_TOO_LARGE),
        (job_requirement_service.TASK_EXISTS, status.HTTP_409_CONFLICT),
        (job_requirement_service.IDEMPOTENCY_CONFLICT, status.HTTP_409_CONFLICT),
        (job_requirement_service.CREATION_RATE_LIMITED, status.HTTP_429_TOO_MANY_REQUESTS),
        (job_requirement_service.DRAFT_EXISTS, status.HTTP_409_CONFLICT),
        (job_requirement_service.CONFIGURATION_NOT_READY, status.HTTP_409_CONFLICT),
    ],
)
def test_create_task_maps_stable_business_errors(
    monkeypatch: MonkeyPatch,
    code: str,
    expected_status: int,
) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_service.RequirementGenerationError(code)

    monkeypatch.setattr(job_requirement_service, "create_parsing_task", reject)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-parsing-tasks",
        json={
            "idempotency_key": IDEMPOTENCY_KEY,
            "sources": [{"source_id": "job-description", "corrected_text": "描述"}],
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": code}


def test_confirm_draft_requires_manage(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_requirement_version_service, "confirm_draft", should_not_run)
    response = make_client(frozenset({"jobs:read"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/confirm",
        json={"expected_revision": 1},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_write_denial_records_tenant_audit(monkeypatch: MonkeyPatch) -> None:
    recorded: list[dict[str, object]] = []

    def capture_audit(_session: object, **kwargs: object) -> None:
        recorded.append(kwargs)

    async def not_writable(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(tenant_audit_service, "record_event", capture_audit)
    monkeypatch.setattr(usage_service, "is_tenant_writable", not_writable)

    context = make_context(frozenset({"jobs:read"}))
    app = create_app(checks=())

    async def commit() -> None:
        return None

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace(commit=commit)))

    async def override_context() -> TenantContext:
        return context

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_tenant_context] = override_context
    client = TestClient(app)

    response = client.post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/confirm",
        json={"expected_revision": 1},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "permission_denied"}
    assert recorded == [
        {
            "tenant_id": TENANT_ID,
            "actor_user_id": USER_ID,
            "action": "job_requirement.write_denied",
            "target_type": "job",
            "target_id": str(JOB_ID),
            "result": "failure",
            "detail": "permission_denied",
        }
    ]


def test_confirm_draft_returns_version(monkeypatch: MonkeyPatch) -> None:
    version_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    async def fake_confirm(*_args: object, **_kwargs: object) -> object:
        draft = draft_view(revision=2)
        draft = replace(draft, status="confirmed", read_only_reason="draft_not_editable")
        return job_requirement_version_service.ConfirmRequirementView(
            version=job_requirement_service.RequirementVersionView(
                id=version_id,
                version_number=1,
                requirement_schema_version_id="job-requirement-schema-v2",
                result=draft.result,
                draft_id=DRAFT_ID,
                input_snapshot_id=SNAPSHOT_ID,
                source_version_id=None,
                confirmed_by=USER_ID,
                confirmed_at=NOW,
                created_at=NOW,
                is_current=True,
            ),
            draft=job_requirement_service.RequirementDraftView(**vars(draft)),
        )

    monkeypatch.setattr(job_requirement_version_service, "confirm_draft", fake_confirm)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/confirm",
        json={"expected_revision": 1},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["version"]["version_number"] == 1
    assert body["version"]["is_current"] is True
    assert body["draft"]["status"] == "confirmed"


def test_confirm_draft_maps_confirmability_errors(monkeypatch: MonkeyPatch) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_version_service.RequirementVersionError(
            job_requirement_version_service.SOURCE_CONFLICTS_UNRESOLVED
        )

    monkeypatch.setattr(job_requirement_version_service, "confirm_draft", reject)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/confirm",
        json={"expected_revision": 1},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "source_conflicts_unresolved"}


def test_copy_current_version_returns_draft(monkeypatch: MonkeyPatch) -> None:
    async def fake_copy(*_args: object, **_kwargs: object) -> object:
        return draft_view(revision=1)

    monkeypatch.setattr(job_requirement_version_service, "copy_current_version", fake_copy)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-versions/copy-current"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(DRAFT_ID)
    assert response.json()["revision"] == 1


def test_list_versions_requires_read(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_requirement_version_service, "list_versions", should_not_run)
    response = make_client(frozenset()).get(f"/jobs/{JOB_ID}/requirement-versions")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_versions_returns_history(monkeypatch: MonkeyPatch) -> None:
    version_id = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    async def fake_list(*_args: object, **_kwargs: object) -> object:
        return version_id, [
            job_requirement_service.RequirementVersionView(
                id=version_id,
                version_number=1,
                requirement_schema_version_id="job-requirement-schema-v2",
                result={},
                draft_id=DRAFT_ID,
                input_snapshot_id=SNAPSHOT_ID,
                source_version_id=None,
                confirmed_by=USER_ID,
                confirmed_at=NOW,
                created_at=NOW,
                is_current=True,
            )
        ]

    monkeypatch.setattr(job_requirement_version_service, "list_versions", fake_list)
    response = make_client(frozenset({"jobs:read"})).get(f"/jobs/{JOB_ID}/requirement-versions")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body[0]["version_number"] == 1
    assert body[0]["is_current"] is True


def upgrade_record_view() -> job_requirement_draft_service.SchemaUpgradeRecordView:
    return job_requirement_draft_service.SchemaUpgradeRecordView(
        id=UPGRADE_ID,
        draft_id=DRAFT_ID,
        from_schema_version_id="job-requirement-schema-v1",
        to_schema_version_id="job-requirement-schema-v2",
        converter_version="v1-to-v2@1",
        item_mappings=[
            {
                "item_id": str(RESOLUTION_ITEM_ID),
                "kind": "hard_condition",
                "mapping": "copied",
                "lossless": True,
            }
        ],
        lossy_resolutions=[],
        actor_user_id=USER_ID,
        created_at=NOW,
    )


def test_schema_upgrade_returns_draft_and_upgrade_record(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_upgrade(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return job_requirement_draft_service.SchemaUpgradeResultView(
            draft=draft_view(revision=2),
            upgrade=upgrade_record_view(),
        )

    monkeypatch.setattr(job_requirement_draft_service, "upgrade_draft_schema", fake_upgrade)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrade",
        json={"expected_revision": 1},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["draft"]["revision"] == 2
    assert body["draft"]["pending_upgrade_items"] == []
    assert body["upgrade"]["id"] == str(UPGRADE_ID)
    assert body["upgrade"]["from_schema_version_id"] == "job-requirement-schema-v1"
    assert body["upgrade"]["to_schema_version_id"] == "job-requirement-schema-v2"
    assert body["upgrade"]["converter_version"] == "v1-to-v2@1"
    assert captured == {
        "tenant_id": TENANT_ID,
        "job_id": JOB_ID,
        "draft_id": DRAFT_ID,
        "actor_user_id": USER_ID,
        "expected_revision": 1,
    }


def test_schema_upgrade_requires_manage_and_writable_tenant(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        message = "service should not run"
        raise AssertionError(message)

    monkeypatch.setattr(job_requirement_draft_service, "upgrade_draft_schema", should_not_run)
    path = f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrade"
    forbidden = make_client(frozenset({"jobs:read"})).post(path, json={"expected_revision": 1})
    read_only = make_client(frozenset({"jobs:manage"}), writable=False).post(
        path,
        json={"expected_revision": 1},
    )

    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden.json() == {"detail": "permission_denied"}
    assert read_only.status_code == status.HTTP_403_FORBIDDEN
    assert read_only.json() == {"detail": "subscription_read_only"}


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        (
            job_requirement_draft_service.SCHEMA_UPGRADE_UNAVAILABLE,
            status.HTTP_409_CONFLICT,
        ),
        (
            job_requirement_draft_service.DRAFT_INVALID,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ),
        (job_requirement_draft_service.DRAFT_NOT_FOUND, status.HTTP_404_NOT_FOUND),
    ],
)
def test_schema_upgrade_maps_stable_business_errors(
    monkeypatch: MonkeyPatch,
    code: str,
    expected_status: int,
) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_draft_service.RequirementDraftError(code)

    monkeypatch.setattr(job_requirement_draft_service, "upgrade_draft_schema", reject)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrade",
        json={"expected_revision": 1},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": code}


def test_schema_upgrade_revision_conflict_returns_the_latest_draft(
    monkeypatch: MonkeyPatch,
) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_draft_service.RequirementDraftError(
            job_requirement_draft_service.DRAFT_REVISION_CONFLICT,
            latest=draft_view(revision=5),
        )

    monkeypatch.setattr(job_requirement_draft_service, "upgrade_draft_schema", reject)
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrade",
        json={"expected_revision": 1},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == job_requirement_draft_service.DRAFT_REVISION_CONFLICT
    assert response.json()["draft"]["revision"] == 5


def test_resolve_schema_upgrade_applies_member_submissions(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_resolve(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return draft_view(revision=3)

    monkeypatch.setattr(
        job_requirement_draft_service,
        "resolve_schema_upgrade_lossy_items",
        fake_resolve,
    )
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrades/{UPGRADE_ID}/resolve",
        json={
            "expected_revision": 2,
            "resolutions": [{"item_id": str(RESOLUTION_ITEM_ID), "resolution": "drop"}],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["revision"] == 3
    assert captured["upgrade_id"] == UPGRADE_ID
    assert captured["expected_revision"] == 2
    assert captured["resolutions"] == [
        job_requirement_draft_service.LossyResolutionSubmission(
            item_id=str(RESOLUTION_ITEM_ID),
            resolution="drop",
        )
    ]


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        (
            job_requirement_draft_service.SCHEMA_UPGRADE_RESOLUTION_INVALID,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ),
        (
            job_requirement_draft_service.SCHEMA_UPGRADE_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
        ),
    ],
)
def test_resolve_schema_upgrade_maps_stable_business_errors(
    monkeypatch: MonkeyPatch,
    code: str,
    expected_status: int,
) -> None:
    async def reject(*_args: object, **_kwargs: object) -> object:
        raise job_requirement_draft_service.RequirementDraftError(code)

    monkeypatch.setattr(
        job_requirement_draft_service,
        "resolve_schema_upgrade_lossy_items",
        reject,
    )
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrades/{UPGRADE_ID}/resolve",
        json={
            "expected_revision": 2,
            "resolutions": [{"item_id": str(RESOLUTION_ITEM_ID), "resolution": "drop"}],
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": code}


def test_resolve_schema_upgrade_rejects_unknown_resolution_choice() -> None:
    response = make_client(frozenset({"jobs:manage"})).post(
        f"/jobs/{JOB_ID}/requirement-drafts/{DRAFT_ID}/schema-upgrades/{UPGRADE_ID}/resolve",
        json={
            "expected_revision": 2,
            "resolutions": [{"item_id": str(RESOLUTION_ITEM_ID), "resolution": "keep"}],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def history_view() -> job_requirement_history_service.RequirementHistoryView:
    return job_requirement_history_service.RequirementHistoryView(
        tasks=[task_view()],
        drafts=[
            job_requirement_history_service.RequirementHistoryDraftView(
                id=DRAFT_ID,
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
        ],
        versions=[
            job_requirement_service.RequirementVersionSummaryView(
                id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
                version_number=1,
                requirement_schema_version_id="job-requirement-schema-v1",
                draft_id=DRAFT_ID,
                source_version_id=None,
                confirmed_by=USER_ID,
                confirmed_at=NOW,
                created_at=NOW,
                is_current=True,
            )
        ],
        schema_upgrades=[upgrade_record_view()],
        sources=[
            job_requirement_history_service.RequirementHistorySourceView(
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
                body_purged_at=NOW,
            )
        ],
        change_events=[
            TenantAuditEventView(
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
        ],
    )


def test_history_returns_layers_with_source_metadata_and_change_events(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_history(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return history_view()

    monkeypatch.setattr(
        job_requirement_history_service,
        "load_requirement_history",
        fake_history,
    )
    response = make_client(frozenset({"jobs:read"})).get(f"/jobs/{JOB_ID}/requirement-history")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert captured == {"tenant_id": TENANT_ID, "job_id": JOB_ID}
    assert body["tasks"][0]["id"] == str(TASK_ID)
    assert body["drafts"][0]["id"] == str(DRAFT_ID)
    assert body["versions"][0]["is_current"] is True
    assert body["schema_upgrades"][0]["converter_version"] == "v1-to-v2@1"
    source = body["sources"][0]
    assert source["body_purged_at"] is not None
    assert "original_text" not in source
    assert "corrected_text" not in source
    assert "sent_text" not in source
    event = body["change_events"][0]
    assert event["action"] == "job_requirement.write_denied"
    assert event["target_id"] == str(JOB_ID)


def test_history_requires_jobs_read(monkeypatch: MonkeyPatch) -> None:
    async def should_not_run(*_args: object, **_kwargs: object) -> object:
        message = "service should not run"
        raise AssertionError(message)

    monkeypatch.setattr(
        job_requirement_history_service,
        "load_requirement_history",
        should_not_run,
    )
    response = make_client(frozenset()).get(f"/jobs/{JOB_ID}/requirement-history")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "permission_denied"}


def test_history_unknown_job_returns_404(monkeypatch: MonkeyPatch) -> None:
    async def not_found(*_args: object, **_kwargs: object) -> object:
        raise JobNotFoundError

    monkeypatch.setattr(job_requirement_history_service, "load_requirement_history", not_found)
    response = make_client(frozenset({"jobs:read"})).get(f"/jobs/{JOB_ID}/requirement-history")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": JOB_NOT_FOUND_DETAIL}
