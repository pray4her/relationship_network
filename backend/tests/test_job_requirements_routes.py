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

from relationship_network_api import job_requirement_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import TenantContext, get_db_session, get_tenant_context
from relationship_network_api.main import create_app
from relationship_network_api.routers import job_requirements

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
    if "jobs:manage" in permissions:

        async def override_manage() -> TenantContext:
            if not writable:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="subscription_read_only",
                )
            return context

        app.dependency_overrides[job_requirements.require_requirement_jobs_manage] = override_manage
    return TestClient(app)


def task_view() -> job_requirement_service.RequirementTaskView:
    return job_requirement_service.RequirementTaskView(
        id=TASK_ID,
        status="queued",
        error_code=None,
        input_snapshot_id=SNAPSHOT_ID,
        configuration_version_id=CONFIGURATION_ID,
        external_call_count=0,
        structured_invalid_count=0,
        created_by=USER_ID,
        created_at=NOW,
        started_at=None,
        completed_at=None,
        next_attempt_at=None,
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
