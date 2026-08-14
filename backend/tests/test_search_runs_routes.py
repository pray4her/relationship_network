"""Route-level tests for the natural-language search run boundary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from relationship_network_api import search_run_service as service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_db_session,
    get_settings,
    get_tenant_context,
)
from relationship_network_api.main import create_app
from relationship_network_api.routers import search_runs

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from _pytest.monkeypatch import MonkeyPatch
    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
RUN_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)


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

    async def override_settings() -> SimpleNamespace:
        return SimpleNamespace()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_tenant_context] = override_context
    app.dependency_overrides[get_settings] = override_settings

    async def override_run() -> TenantContext:
        if "search:run" not in permissions:
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

    app.dependency_overrides[search_runs.require_search_run_audited] = override_run
    return TestClient(app)


def run_view() -> service.SearchRunView:
    return service.SearchRunView(
        id=RUN_ID,
        status="succeeded",
        failure_reason=None,
        utterance="找 AI 研究员",
        utterance_length=6,
        idempotency_key="client-key",
        llm_configuration_version_id=uuid.UUID("66666666-6666-4666-8666-666666666666"),
        search_contract_version="v1",
        data_version="data-v1",
        request_id="req-1",
        has_research_topic=True,
        search_interpretation={
            "hard_conditions": [],
            "research_topic_query": "AI",
            "unsupported_conditions": [],
        },
        created_at=NOW,
    )


def test_create_requires_search_run_permission(monkeypatch: MonkeyPatch) -> None:
    def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "run_search", should_not_run)
    response = make_client(frozenset()).post(
        "/search/runs",
        json={"utterance": "AI", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "permission_denied"}


def test_create_requires_writable_tenant(monkeypatch: MonkeyPatch) -> None:
    def should_not_run(*_args: object, **_kwargs: object) -> object:
        msg = "service should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "run_search", should_not_run)
    response = make_client(frozenset({"search:run"}), writable=False).post(
        "/search/runs",
        json={"utterance": "AI", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "subscription_read_only"}


def test_create_maps_invalid_utterance_to_400(monkeypatch: MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> service.SearchRunView:
        raise service.InvalidUtteranceError

    monkeypatch.setattr(service, "run_search", fail)
    response = make_client(frozenset({"search:run"})).post(
        "/search/runs",
        json={"utterance": "   ", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "invalid_utterance"}


def test_create_maps_idempotency_conflict_to_409(monkeypatch: MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> service.SearchRunView:
        raise service.SearchIdempotencyConflictError

    monkeypatch.setattr(service, "run_search", fail)
    response = make_client(frozenset({"search:run"})).post(
        "/search/runs",
        json={"utterance": "AI", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "search_idempotency_fingerprint_conflict"}


def test_create_maps_rate_limit_to_429(monkeypatch: MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> service.SearchRunView:
        raise service.SearchCreationRateLimitedError

    monkeypatch.setattr(service, "run_search", fail)
    response = make_client(frozenset({"search:run"})).post(
        "/search/runs",
        json={"utterance": "AI", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json() == {"detail": "search_creation_rate_limited"}


def test_create_maps_quota_to_409(monkeypatch: MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> service.SearchRunView:
        raise service.SearchQuotaExceededError(RUN_ID)

    monkeypatch.setattr(service, "run_search", fail)
    response = make_client(frozenset({"search:run"})).post(
        "/search/runs",
        json={"utterance": "AI", "idempotency_key": "k"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "search_quota_exceeded"}


def test_create_returns_201_with_run(monkeypatch: MonkeyPatch) -> None:
    async def succeed(*_args: object, **_kwargs: object) -> service.SearchRunView:
        return run_view()

    monkeypatch.setattr(service, "run_search", succeed)
    response = make_client(frozenset({"search:run"})).post(
        "/search/runs",
        json={"utterance": "找 AI 研究员", "idempotency_key": "client-key"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["id"] == str(RUN_ID)
    assert body["status"] == "succeeded"
    assert body["utterance"] == "找 AI 研究员"


def test_list_requires_search_read() -> None:
    response = make_client(frozenset()).get("/search/runs")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_returns_runs(monkeypatch: MonkeyPatch) -> None:
    async def page(*_args: object, **_kwargs: object) -> service.SearchRunListPage:
        return service.SearchRunListPage(runs=(run_view(),), next_cursor=None)

    monkeypatch.setattr(service, "list_runs", page)
    response = make_client(frozenset({"search:read"})).get("/search/runs")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["runs"][0]["id"] == str(RUN_ID)
    assert response.json()["next_cursor"] is None


def test_get_maps_not_found_to_404(monkeypatch: MonkeyPatch) -> None:
    async def missing(*_args: object, **_kwargs: object) -> service.SearchRunDetail:
        raise service.SearchRunNotFoundError

    monkeypatch.setattr(service, "get_run", missing)
    response = make_client(frozenset({"search:read"})).get(f"/search/runs/{RUN_ID}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "search_run_not_found"}


def test_get_returns_detail_with_sort_marker(monkeypatch: MonkeyPatch) -> None:
    async def detail(*_args: object, **_kwargs: object) -> service.SearchRunDetail:
        return service.SearchRunDetail(
            run=run_view(),
            hits=(),
            next_cursor=None,
            total=0,
            sorted_by="h_index",
            left_relevance_order=True,
        )

    monkeypatch.setattr(service, "get_run", detail)
    response = make_client(frozenset({"search:read"})).get(
        f"/search/runs/{RUN_ID}?sort=h_index"
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["sorted_by"] == "h_index"
    assert body["left_relevance_order"] is True
