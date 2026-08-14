import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import llm_configuration_service as service
from relationship_network_api.auth_service import Authentication, UserView
from relationship_network_api.deps import get_db_session, require_platform_admin
from relationship_network_api.main import create_app
from relationship_network_api.models import LlmConfigurationAttemptStatus

if TYPE_CHECKING:
    from relationship_network_api.openrouter import CandidateConfiguration

ADMIN_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CURRENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ATTEMPT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
NOW = datetime(2026, 8, 11, tzinfo=UTC)


def authentication() -> Authentication:
    return Authentication(
        user=UserView(
            id=ADMIN_ID,
            email="admin@example.com",
            display_name="平台管理员",
            is_platform_admin=True,
        ),
        membership=None,
        expires_at=NOW,
        renewed=False,
    )


def attempt_view(
    status: LlmConfigurationAttemptStatus = "queued",
) -> service.LlmConfigurationAttemptView:
    return service.LlmConfigurationAttemptView(
        id=ATTEMPT_ID,
        status=status,
        candidate={
            "call_bindings": {
                "job_requirement_parsing": {
                    "prompt_version_id": "job-requirement-prompt-v1",
                    "request_timeout_seconds": 180,
                },
                "search_interpretation": {
                    "prompt_version_id": "search-interpretation-prompt-v1",
                    "request_timeout_seconds": 15,
                },
            },
            "model": "x-ai/grok-4.5",
            "prompt_version_id": "job-requirement-prompt-v1",
            "temperature": 0,
            "max_output_tokens": 8192,
            "request_timeout_seconds": 180,
        },
        expected_current_version_id=CURRENT_ID,
        source_version_id=None,
        external_call_count=0,
        structured_invalid_count=0,
        probe_progress={},
        next_attempt_at=None,
        error_code=None,
        created_by=ADMIN_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def client() -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", object())

    async def override_admin() -> Authentication:
        return authentication()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[require_platform_admin] = override_admin
    return TestClient(app)


def candidate_payload() -> dict[str, object]:
    return {
        "call_bindings": {
            "job_requirement_parsing": {
                "prompt_version_id": "job-requirement-prompt-v1",
                "request_timeout_seconds": 180,
            },
            "search_interpretation": {
                "prompt_version_id": "search-interpretation-prompt-v1",
                "request_timeout_seconds": 15,
            },
        },
        "expected_current_version_id": str(CURRENT_ID),
        "max_output_tokens": 8192,
        "model": "x-ai/grok-4.5",
        "temperature": 0,
    }


def test_create_attempt_returns_202_and_only_the_explicit_candidate(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_create(
        _session: AsyncSession,
        *,
        candidate: object,
        expected_current_version_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> service.LlmConfigurationAttemptView:
        captured.update(
            candidate=cast("CandidateConfiguration", candidate).sanitized_snapshot(),
            current=expected_current_version_id,
            actor=actor_id,
        )
        return attempt_view()

    monkeypatch.setattr(service, "create_attempt", fake_create)

    response = client().post("/admin/llm-configuration-attempts", json=candidate_payload())

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert captured["candidate"] == {
        "call_bindings": {
            "job_requirement_parsing": {
                "prompt_version_id": "job-requirement-prompt-v1",
                "request_timeout_seconds": 180,
            },
            "search_interpretation": {
                "prompt_version_id": "search-interpretation-prompt-v1",
                "request_timeout_seconds": 15,
            },
        },
        "max_output_tokens": 8192,
        "model": "x-ai/grok-4.5",
        "prompt_version_id": "job-requirement-prompt-v1",
        "request_timeout_seconds": 180,
        "temperature": 0,
    }
    assert captured["current"] == CURRENT_ID
    assert captured["actor"] == ADMIN_ID


def test_create_attempt_rejects_unknown_fields_before_service(
    monkeypatch: MonkeyPatch,
) -> None:
    called = False

    async def fake_create(*_args: object, **_kwargs: object) -> service.LlmConfigurationAttemptView:
        nonlocal called
        called = True
        return attempt_view()

    monkeypatch.setattr(service, "create_attempt", fake_create)
    payload = candidate_payload()
    payload["api_key"] = "must-never-cross-the-boundary"

    response = client().post("/admin/llm-configuration-attempts", json=payload)

    assert response.status_code == 422
    assert called is False


def test_create_attempt_exposes_stable_conflict_codes(monkeypatch: MonkeyPatch) -> None:
    async def stale(*_args: object, **_kwargs: object) -> service.LlmConfigurationAttemptView:
        raise service.StaleCurrentConfigurationError(service.STALE_CURRENT_CONFIGURATION)

    monkeypatch.setattr(service, "create_attempt", stale)

    response = client().post("/admin/llm-configuration-attempts", json=candidate_payload())

    assert response.status_code == 409
    assert response.json() == {"detail": "stale_current_configuration"}


def test_create_attempt_returns_existing_active_attempt_on_single_flight_conflict(
    monkeypatch: MonkeyPatch,
) -> None:
    async def active(*_args: object, **_kwargs: object) -> service.LlmConfigurationAttemptView:
        raise service.ConfigChangeInProgressError(ATTEMPT_ID)

    monkeypatch.setattr(service, "create_attempt", active)

    response = client().post("/admin/llm-configuration-attempts", json=candidate_payload())

    assert response.status_code == 409
    assert response.json() == {
        "attempt_id": str(ATTEMPT_ID),
        "detail": "config_change_in_progress",
    }


def test_sse_replays_after_last_event_id_and_closes_on_terminal(
    monkeypatch: MonkeyPatch,
) -> None:
    requested_after: list[int] = []

    async def fake_get(*_args: object, **_kwargs: object) -> service.LlmConfigurationAttemptView:
        return attempt_view(status="succeeded")

    async def fake_events(
        _session: AsyncSession,
        *,
        attempt_id: uuid.UUID,
        after_sequence: int,
    ) -> list[service.LlmConfigurationAttemptEventView]:
        assert attempt_id == ATTEMPT_ID
        requested_after.append(after_sequence)
        return [
            service.LlmConfigurationAttemptEventView(
                attempt_id=ATTEMPT_ID,
                sequence_number=3,
                event_type="succeeded",
                payload={"configuration_version_id": str(CURRENT_ID)},
                created_at=NOW,
            )
        ]

    monkeypatch.setattr(service, "get_attempt", fake_get)
    monkeypatch.setattr(service, "list_attempt_events", fake_events)

    response = client().get(
        f"/admin/llm-configuration-attempts/{ATTEMPT_ID}/events",
        headers={"Last-Event-ID": "2"},
    )

    assert response.status_code == 200
    assert requested_after == [2]
    assert "id: 3\nevent: succeeded\n" in response.text
    data_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: "))["status"] == "succeeded"


def test_create_attempt_rejects_parsing_timeout_below_minimum() -> None:
    payload = candidate_payload()
    cast("dict[str, object]", payload["call_bindings"])["job_requirement_parsing"] = {
        "prompt_version_id": "job-requirement-prompt-v1",
        "request_timeout_seconds": 29,
    }

    response = client().post("/admin/llm-configuration-attempts", json=payload)

    assert response.status_code == 422


def test_create_attempt_rejects_search_timeout_above_maximum() -> None:
    payload = candidate_payload()
    cast("dict[str, object]", payload["call_bindings"])["search_interpretation"] = {
        "prompt_version_id": "search-interpretation-prompt-v1",
        "request_timeout_seconds": 31,
    }

    response = client().post("/admin/llm-configuration-attempts", json=payload)

    assert response.status_code == 422
