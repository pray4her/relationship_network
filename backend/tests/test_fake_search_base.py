import json

import httpx
import pytest

from relationship_network_api.fake_search_base import (
    DEFAULT_DATA_VERSION,
    DEFAULT_SERVICE_API_KEY,
    SEEDED_ABSENT_PERSON_ID,
    SEEDED_PERSON_ID,
    SEEDED_PERSONS,
    app,
    reset_fake_search_base,
    state,
)
from relationship_network_api.search_base_contract import (
    AUTHORIZATION_HEADER,
    BEARER_SCHEME,
    CONTRACT_VERSION_HEADER,
    EXECUTABLE_SCHEMA_VERSIONS,
    MAX_PERSON_BATCH_SIZE,
    REQUEST_ID_HEADER,
    SEARCH_CONTRACT_VERSION_V1,
    PersonBatchResponse,
    PersonCurrentAbsence,
    PersonDetailFound,
    SearchBaseErrorBody,
    SearchBaseHealthResponse,
)


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    reset_fake_search_base()


def _health_headers(
    *,
    api_key: str = DEFAULT_SERVICE_API_KEY,
    contract_version: str = SEARCH_CONTRACT_VERSION_V1,
) -> dict[str, str]:
    return {
        AUTHORIZATION_HEADER: f"{BEARER_SCHEME} {api_key}",
        CONTRACT_VERSION_HEADER: contract_version,
        REQUEST_ID_HEADER: "req-fake-1",
    }


@pytest.mark.anyio
async def test_liveness_does_not_require_service_credentials() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_authenticated_health_round_trips_contract_models() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/v1/health", headers=_health_headers())

    payload = SearchBaseHealthResponse.model_validate(response.json())
    assert payload.request_id == "req-fake-1"
    assert payload.contract_version == SEARCH_CONTRACT_VERSION_V1
    assert payload.executable_schema_versions == EXECUTABLE_SCHEMA_VERSIONS
    assert payload.data_version == DEFAULT_DATA_VERSION
    assert payload.status == "ok"


@pytest.mark.anyio
async def test_scenario_switches_cover_auth_version_throttle_and_unavailable() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing = await client.get("/v1/health")
        state.deny_auth = True
        denied = await client.get("/v1/health", headers=_health_headers())
        reset_fake_search_base()
        state.forbidden = True
        forbidden = await client.get("/v1/health", headers=_health_headers())
        reset_fake_search_base()
        mismatched = await client.get(
            "/v1/health",
            headers=_health_headers(contract_version="v0"),
        )
        reset_fake_search_base()
        state.rate_limited = True
        state.retry_after_seconds = 4
        limited = await client.get("/v1/health", headers=_health_headers())
        reset_fake_search_base()
        state.status_5xx = True
        unavailable = await client.get("/v1/health", headers=_health_headers())

    assert SearchBaseErrorBody.model_validate(missing.json()) == SearchBaseErrorBody(
        category="unauthenticated",
        retryable=False,
    )
    assert missing.status_code == 401
    assert SearchBaseErrorBody.model_validate(denied.json()).category == "unauthenticated"
    assert forbidden.status_code == 403
    assert SearchBaseErrorBody.model_validate(forbidden.json()).category == "forbidden"
    assert mismatched.status_code == 409
    assert (
        SearchBaseErrorBody.model_validate(mismatched.json()).category
        == "contract_version_incompatible"
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "4"
    assert unavailable.status_code == 500
    assert SearchBaseErrorBody.model_validate(unavailable.json()).category == "unavailable"


@pytest.mark.anyio
async def test_hang_seconds_are_controllable_without_production_timeouts() -> None:
    state.hang_seconds = 0.01
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        timeout=1,
    ) as client:
        response = await client.get("/v1/health", headers=_health_headers())

    assert response.status_code == 200
    assert SearchBaseHealthResponse.model_validate(response.json()).request_id == "req-fake-1"


def _assert_no_contact_keys(payload: object) -> None:
    blob = json.dumps(payload).lower()
    for key in ("email", "e-mail", "phone", "telephone", "mobile", "tel"):
        assert f'"{key}"' not in blob


@pytest.mark.anyio
async def test_person_detail_round_trips_found_contract_model() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/v1/persons/{SEEDED_PERSON_ID}",
            headers=_health_headers(),
        )

    assert response.status_code == 200
    payload = PersonDetailFound.model_validate(response.json())
    assert payload.outcome == "found"
    assert payload.person == SEEDED_PERSONS[SEEDED_PERSON_ID]
    assert payload.data_version == DEFAULT_DATA_VERSION
    _assert_no_contact_keys(response.json())


@pytest.mark.anyio
async def test_person_detail_current_absence_is_http_200() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/v1/persons/{SEEDED_ABSENT_PERSON_ID}",
            headers=_health_headers(),
        )

    assert response.status_code == 200
    payload = PersonCurrentAbsence.model_validate(response.json())
    assert payload.outcome == "current_absence"
    assert payload.canonical_person_id == SEEDED_ABSENT_PERSON_ID
    assert "person" not in response.json()
    _assert_no_contact_keys(response.json())


@pytest.mark.anyio
async def test_person_batch_round_trips_found_and_absent() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/persons/batch",
            headers=_health_headers(),
            json={"canonical_person_ids": [SEEDED_PERSON_ID, SEEDED_ABSENT_PERSON_ID]},
        )

    assert response.status_code == 200
    payload = PersonBatchResponse.model_validate(response.json())
    assert payload.persons == (SEEDED_PERSONS[SEEDED_PERSON_ID],)
    assert payload.currently_absent_ids == (SEEDED_ABSENT_PERSON_ID,)
    _assert_no_contact_keys(response.json())


@pytest.mark.anyio
async def test_person_batch_over_limit_is_invalid_query() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/persons/batch",
            headers=_health_headers(),
            json={
                "canonical_person_ids": [
                    f"cp-{index}" for index in range(MAX_PERSON_BATCH_SIZE + 1)
                ]
            },
        )

    assert response.status_code == 400
    assert SearchBaseErrorBody.model_validate(response.json()) == SearchBaseErrorBody(
        category="invalid_query",
        retryable=False,
    )


@pytest.mark.anyio
async def test_person_detail_uses_shared_auth_guard() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing = await client.get(f"/v1/persons/{SEEDED_PERSON_ID}")
        denied = await client.get(
            f"/v1/persons/{SEEDED_PERSON_ID}",
            headers=_health_headers(api_key="wrong-key"),
        )

    assert missing.status_code == 401
    assert denied.status_code == 401
    assert SearchBaseErrorBody.model_validate(missing.json()).category == "unauthenticated"
