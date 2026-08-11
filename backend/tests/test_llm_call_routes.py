import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import llm_call_diagnostics_service as service
from relationship_network_api.auth_service import Authentication, UserView
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import get_db_session, require_platform_admin
from relationship_network_api.main import create_app
from relationship_network_api.models import LlmCallRecord

ADMIN_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CALL_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
ATTEMPT_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
NOW = datetime(2026, 8, 11, tzinfo=UTC)


def settings() -> AppSettings:
    return AppSettings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:password@localhost/db",
            "llm_raw_response_keys": "{}",
            "object_storage_access_key": "access",
            "object_storage_secret_key": "secret",
        }
    )


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


def client() -> TestClient:
    app = create_app(checks=(), settings=settings())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", object())

    async def override_admin() -> Authentication:
        return authentication()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[require_platform_admin] = override_admin
    return TestClient(app)


def call_record() -> LlmCallRecord:
    return LlmCallRecord(
        id=CALL_ID,
        scope="platform",
        tenant_id=None,
        scope_key="platform",
        call_type="config_probe",
        platform_attempt_id=ATTEMPT_ID,
        job_requirement_parsing_task_id=None,
        configuration_version_id=None,
        input_snapshot_id=None,
        correlation_call_id=None,
        request_number=1,
        model="x-ai/grok-4.5",
        prompt_version_id="prompt-v1",
        prompt_sha256="a" * 64,
        requirement_schema_version_id="schema-v1",
        requirement_schema_sha256="b" * 64,
        input_sources_summary={"kind": "fixed_platform_probe"},
        input_sha256="c" * 64,
        input_length=42,
        parameters={"temperature": 0},
        request_hash="d" * 64,
        created_at=NOW,
    )


def test_list_supports_filters_and_returns_keyset_cursor(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_list(_session: object, **kwargs: object) -> service.LlmCallPageView:
        captured.update(kwargs)
        return service.LlmCallPageView(
            calls=[
                service.LlmCallSummaryView(
                    id=CALL_ID,
                    scope="platform",
                    tenant_id=None,
                    call_type="config_probe",
                    model="x-ai/grok-4.5",
                    request_number=1,
                    platform_attempt_id=ATTEMPT_ID,
                    job_requirement_parsing_task_id=None,
                    outcome="succeeded",
                    metadata_status="available",
                    raw_response_available=True,
                    created_at=NOW,
                )
            ],
            next_cursor="next-page",
        )

    monkeypatch.setattr(service, "list_calls", fake_list)
    response = client().get(
        "/admin/llm-calls",
        params={
            "scope": "platform",
            "call_type": "config_probe",
            "outcome": "succeeded",
            "metadata_status": "available",
            "platform_attempt_id": str(ATTEMPT_ID),
        },
    )

    assert response.status_code == 200
    assert response.json()["next_cursor"] == "next-page"
    assert response.json()["calls"][0]["raw_response_available"] is True
    assert captured["scope"] == "platform"
    assert captured["platform_attempt_id"] == ATTEMPT_ID


def test_detail_exposes_facts_but_never_ciphertext_or_nonce(monkeypatch: MonkeyPatch) -> None:
    async def fake_detail(*_args: object, **_kwargs: object) -> service.LlmCallDetailView:
        return service.LlmCallDetailView(
            call=call_record(),
            outcomes=[
                service.LlmCallOutcomeView(
                    sequence_number=1,
                    outcome="succeeded",
                    category="",
                    provider_request_id="gen-1",
                    actual_model="x-ai/grok-4.5",
                    actual_provider="provider-a",
                    http_status=200,
                    duration_ms=123,
                    created_at=NOW,
                )
            ],
            metadata_events=[],
            raw_response_available=True,
            raw_response_expires_at=NOW,
        )

    monkeypatch.setattr(service, "get_call_detail", fake_detail)
    response = client().get(f"/admin/llm-calls/{CALL_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["call"]["input_length"] == 42
    assert body["outcomes"][0]["duration_ms"] == 123
    assert "ciphertext" not in response.text
    assert "nonce" not in response.text


def test_raw_response_is_explicit_no_store_and_maps_stable_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_success(*_args: object, **_kwargs: object) -> service.DecryptedRawResponseView:
        return service.DecryptedRawResponseView(
            body='{"capability":"ok"}',
            encoding="utf-8",
            content_type="application/json",
            http_status=200,
            response_sequence=1,
            created_at=NOW,
            expires_at=NOW,
        )

    monkeypatch.setattr(service, "view_raw_response", fake_success)
    response = client().post(f"/admin/llm-calls/{CALL_ID}/raw-response")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["body"] == '{"capability":"ok"}'

    async def missing(*_args: object, **_kwargs: object) -> service.DecryptedRawResponseView:
        raise service.LlmRawResponseNotFoundError(service.RAW_RESPONSE_NOT_FOUND)

    monkeypatch.setattr(service, "view_raw_response", missing)
    response = client().post(f"/admin/llm-calls/{CALL_ID}/raw-response")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "llm_raw_response_not_found"}

    async def key_missing(*_args: object, **_kwargs: object) -> service.DecryptedRawResponseView:
        raise service.LlmRawResponseKeyUnavailableError(service.RAW_RESPONSE_KEY_UNAVAILABLE)

    monkeypatch.setattr(service, "view_raw_response", key_missing)
    response = client().post(f"/admin/llm-calls/{CALL_ID}/raw-response")
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "llm_raw_response_key_unavailable"}
