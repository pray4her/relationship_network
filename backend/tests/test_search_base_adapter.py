import json
from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import ValidationError

from relationship_network_api.fake_search_base import (
    DEFAULT_DATA_VERSION,
    DEFAULT_SERVICE_API_KEY,
    SEEDED_ABSENT_PERSON_ID,
    SEEDED_FIELD_PROVENANCE,
    SEEDED_PERSON_ID,
    SEEDED_PERSON_WITHOUT_RANKS_ID,
    SEEDED_PERSONS,
    SEEDED_PUBLICATION_ID,
    SEEDED_PUBLICATIONS,
    SEEDED_SEARCH_HIT_PUBLICATIONS,
    SEEDED_SEARCH_SEMANTIC_SCORES,
    app,
    reset_fake_search_base,
    state,
)
from relationship_network_api.llm_assets.manifest import JOB_REQUIREMENT_SCHEMA_V1
from relationship_network_api.search_base import (
    MAX_ATTEMPTS,
    SearchBaseAdapter,
    SearchBaseAdapterError,
    SearchBaseClientConfig,
)
from relationship_network_api.search_base_contract import (
    AUTHORIZATION_HEADER,
    BEARER_SCHEME,
    CHINESE_IDENTITY_VALUES,
    CONTRACT_VERSION_HEADER,
    EXECUTABLE_SCHEMA_VERSIONS,
    HARD_CONDITION_FIELD_CATALOG,
    MAX_PERSON_BATCH_SIZE,
    MAX_RESEARCH_TOPIC_QUERY_CHARACTERS,
    REQUEST_ID_HEADER,
    SEARCH_CONTRACT_VERSION_V1,
    HardCondition,
    PersonCurrentAbsence,
    PersonDetailFound,
    PersonEvidenceFound,
    TalentSearchRequest,
    TalentSearchResponse,
)


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    reset_fake_search_base()


@pytest.fixture
async def fake_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://search-base.test",
    ) as client:
        yield client


def _config(**overrides: str | float) -> SearchBaseClientConfig:
    values: dict[str, str | float] = {
        "api_key": DEFAULT_SERVICE_API_KEY,
        "base_url": "http://search-base.test",
        "timeout_seconds": 0.2,
        "contract_version": SEARCH_CONTRACT_VERSION_V1,
    }
    values.update(overrides)
    return SearchBaseClientConfig(
        api_key=str(values["api_key"]),
        base_url=str(values["base_url"]),
        timeout_seconds=float(values["timeout_seconds"]),
        contract_version=str(values["contract_version"]),
    )


async def _noop_sleep(_seconds: float) -> None:
    return None


@pytest.mark.anyio
async def test_health_echoes_request_id_and_declares_executable_schemas(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.check_health(request_id="req-health-1")

    assert result.request_id == "req-health-1"
    assert result.contract_version == SEARCH_CONTRACT_VERSION_V1
    assert result.executable_schema_versions == EXECUTABLE_SCHEMA_VERSIONS
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.status == "ok"
    assert state.last_authorization == f"{BEARER_SCHEME} {DEFAULT_SERVICE_API_KEY}"
    assert state.last_contract_version == SEARCH_CONTRACT_VERSION_V1
    assert state.last_request_id == "req-health-1"
    assert state.request_count == 1


@pytest.mark.anyio
async def test_missing_or_wrong_credentials_are_not_retried(
    fake_client: httpx.AsyncClient,
) -> None:
    missing = SearchBaseAdapter(_config(api_key=""), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as missing_error:
        _ = await missing.check_health(request_id="req-missing")
    assert missing_error.value.category == "unauthenticated"
    assert missing_error.value.retryable is False
    assert missing_error.value.status_code == 401
    assert state.request_count == 1

    reset_fake_search_base()
    wrong = SearchBaseAdapter(_config(api_key="wrong-key"), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as wrong_error:
        _ = await wrong.check_health(request_id="req-wrong")
    assert wrong_error.value.category == "unauthenticated"
    assert wrong_error.value.retryable is False
    assert state.request_count == 1


@pytest.mark.anyio
async def test_forbidden_scenario_is_not_retried(fake_client: httpx.AsyncClient) -> None:
    state.forbidden = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=_noop_sleep)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.check_health(request_id="req-forbidden")

    assert captured.value.category == "forbidden"
    assert captured.value.retryable is False
    assert captured.value.status_code == 403
    assert state.request_count == 1


@pytest.mark.anyio
async def test_incompatible_contract_version_is_not_retried(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(
        _config(contract_version="v0"),
        client=fake_client,
        sleeper=_noop_sleep,
    )
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.check_health(request_id="req-mismatch")

    assert captured.value.category == "contract_version_incompatible"
    assert captured.value.retryable is False
    assert captured.value.status_code == 409
    assert state.last_contract_version == "v0"
    assert state.request_count == 1


@pytest.mark.anyio
async def test_rate_limited_health_retries_three_times_and_honors_retry_after(
    fake_client: httpx.AsyncClient,
) -> None:
    delays: list[float] = []

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    state.rate_limited = True
    state.retry_after_seconds = 7
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=sleeper)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.check_health(request_id="req-429")

    assert captured.value.category == "rate_limited"
    assert captured.value.retryable is True
    assert captured.value.retry_after_seconds == 7
    assert state.request_count == MAX_ATTEMPTS
    assert delays == [7, 7]


@pytest.mark.anyio
async def test_unavailable_health_retries_three_times_with_backoff(
    fake_client: httpx.AsyncClient,
) -> None:
    delays: list[float] = []

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    state.status_5xx = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=sleeper)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.check_health(request_id="req-5xx")

    assert captured.value.category == "unavailable"
    assert captured.value.retryable is True
    assert state.request_count == MAX_ATTEMPTS
    assert delays == [0.2, 0.4]


@pytest.mark.anyio
async def test_timeout_retries_until_attempt_cap() -> None:
    attempts = {"count": 0}
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        message = "timed out"
        raise httpx.ReadTimeout(message)

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=sleeper)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.check_health(request_id="req-timeout")

    assert captured.value.category == "timeout"
    assert captured.value.retryable is True
    assert attempts["count"] == MAX_ATTEMPTS
    assert delays == [0.2, 0.4]


@pytest.mark.anyio
async def test_network_error_is_retryable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        message = "connection dropped"
        raise httpx.ConnectError(message)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.check_health(request_id="req-net")

    assert captured.value.category == "network_error"
    assert captured.value.retryable is True


@pytest.mark.anyio
async def test_missing_required_response_fields_are_invalid_and_not_retried() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        assert request.headers[AUTHORIZATION_HEADER.lower()].startswith(f"{BEARER_SCHEME} ")
        assert request.headers[CONTRACT_VERSION_HEADER.lower()] == SEARCH_CONTRACT_VERSION_V1
        assert request.headers[REQUEST_ID_HEADER.lower()] == "req-invalid"
        return httpx.Response(200, json={"status": "ok", "request_id": "req-invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.check_health(request_id="req-invalid")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False
    assert attempts["count"] == 1


@pytest.mark.anyio
async def test_mismatched_echoed_request_id_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "other-id",
                "contract_version": SEARCH_CONTRACT_VERSION_V1,
                "executable_schema_versions": list(EXECUTABLE_SCHEMA_VERSIONS),
                "data_version": DEFAULT_DATA_VERSION,
                "status": "ok",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.check_health(request_id="req-echo")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_check_health_generates_request_id_when_omitted(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.check_health()

    assert result.request_id == state.last_request_id
    assert result.request_id
    assert result.data_version == DEFAULT_DATA_VERSION


def test_client_config_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        _ = SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url="http://search-base.test",
            timeout_seconds=0,
        )


def test_chinese_identity_values_match_schema_catalog() -> None:
    assert JOB_REQUIREMENT_SCHEMA_V1.chinese_identity_values == CHINESE_IDENTITY_VALUES


def test_hard_condition_catalog_matches_schema_catalog() -> None:
    assert {
        field: frozenset(operators)
        for field, operators in JOB_REQUIREMENT_SCHEMA_V1.field_catalog.items()
    } == HARD_CONDITION_FIELD_CATALOG
    assert (
        JOB_REQUIREMENT_SCHEMA_V1.output_limits["research_topic_query_characters"]
        == MAX_RESEARCH_TOPIC_QUERY_CHARACTERS
    )


@pytest.mark.anyio
async def test_person_detail_returns_seeded_current_fields(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-person-1")

    assert isinstance(result, PersonDetailFound)
    assert result.request_id == "req-person-1"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.person == SEEDED_PERSONS[SEEDED_PERSON_ID]
    assert result.person.chinese_identity in CHINESE_IDENTITY_VALUES
    assert result.person.has_contact is True
    assert result.person.historical_source_ids == ("src-openalex-001", "src-orcid-001")
    assert state.last_request_id == "req-person-1"
    assert state.request_count == 1


@pytest.mark.anyio
async def test_person_detail_omits_ranks_and_marks_no_contact(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person(
        SEEDED_PERSON_WITHOUT_RANKS_ID,
        request_id="req-person-2",
    )

    assert isinstance(result, PersonDetailFound)
    assert result.person.qs_top200_rank is None
    assert result.person.world_top500_rank is None
    assert result.person.has_contact is False


@pytest.mark.anyio
async def test_person_detail_current_absence_is_not_an_empty_person(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person(SEEDED_ABSENT_PERSON_ID, request_id="req-absent-1")

    assert isinstance(result, PersonCurrentAbsence)
    assert result.outcome == "current_absence"
    assert result.canonical_person_id == SEEDED_ABSENT_PERSON_ID
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.request_id == "req-absent-1"
    assert not hasattr(result, "person")


@pytest.mark.anyio
async def test_blank_person_id_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_person("  ", request_id="req-blank")

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_person_batch_partial_success_lists_current_absence(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_persons(
        [SEEDED_PERSON_ID, SEEDED_ABSENT_PERSON_ID, SEEDED_PERSON_WITHOUT_RANKS_ID],
        request_id="req-batch-1",
    )

    assert result.request_id == "req-batch-1"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.persons == (
        SEEDED_PERSONS[SEEDED_PERSON_ID],
        SEEDED_PERSONS[SEEDED_PERSON_WITHOUT_RANKS_ID],
    )
    assert result.currently_absent_ids == (SEEDED_ABSENT_PERSON_ID,)


@pytest.mark.anyio
async def test_empty_person_batch_still_sends_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_persons([], request_id="req-empty-batch")

    assert result.persons == ()
    assert result.currently_absent_ids == ()
    assert result.request_id == "req-empty-batch"
    assert state.request_count == 1


@pytest.mark.anyio
async def test_person_batch_over_limit_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    too_many = [f"cp-{index}" for index in range(MAX_PERSON_BATCH_SIZE + 1)]
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_persons(too_many, request_id="req-over-limit")

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_person_batch_auth_failure_fails_the_whole_batch(
    fake_client: httpx.AsyncClient,
) -> None:
    state.deny_auth = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=_noop_sleep)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_persons([SEEDED_PERSON_ID], request_id="req-batch-auth")

    assert captured.value.category == "unauthenticated"
    assert captured.value.retryable is False
    assert captured.value.status_code == 401
    assert state.request_count == 1


@pytest.mark.anyio
async def test_person_batch_unavailable_retries_then_fails_whole_batch(
    fake_client: httpx.AsyncClient,
) -> None:
    delays: list[float] = []

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    state.status_5xx = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=sleeper)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_persons([SEEDED_PERSON_ID], request_id="req-batch-5xx")

    assert captured.value.category == "unavailable"
    assert captured.value.retryable is True
    assert state.request_count == MAX_ATTEMPTS
    assert delays == [0.2, 0.4]


@pytest.mark.anyio
async def test_person_payload_with_email_is_invalid_and_not_retried() -> None:
    attempts = {"count": 0}
    person = SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json")
    person["email"] = "wei@example.com"

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(
            200,
            json={
                "outcome": "found",
                "request_id": "req-contact",
                "data_version": DEFAULT_DATA_VERSION,
                "person": person,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-contact")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False
    assert attempts["count"] == 1


@pytest.mark.anyio
async def test_person_batch_payload_with_phone_is_invalid_response() -> None:
    person = SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json")
    person["phone"] = "+86-10-0000"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "req-phone",
                "data_version": DEFAULT_DATA_VERSION,
                "persons": [person],
                "currently_absent_ids": [],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_persons([SEEDED_PERSON_ID], request_id="req-phone")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_person_detail_missing_data_version_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "outcome": "found",
                "request_id": "req-missing-dv",
                "person": SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json"),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-missing-dv")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_person_detail_mismatched_request_id_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "outcome": "found",
                "request_id": "other-id",
                "data_version": DEFAULT_DATA_VERSION,
                "person": SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json"),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-echo")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_illegal_chinese_identity_in_response_is_invalid() -> None:
    person = SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json")
    person["chinese_identity"] = "汉族"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "outcome": "found",
                "request_id": "req-identity",
                "data_version": DEFAULT_DATA_VERSION,
                "person": person,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-identity")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_person_evidence_returns_seeded_publications_and_provenance(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence-1")

    assert isinstance(result, PersonEvidenceFound)
    assert result.request_id == "req-evidence-1"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.canonical_person_id == SEEDED_PERSON_ID
    assert result.publications == SEEDED_PUBLICATIONS[SEEDED_PERSON_ID]
    assert result.field_provenance == SEEDED_FIELD_PROVENANCE[SEEDED_PERSON_ID]
    assert result.publications[0].snippet is not None
    assert result.publications[1].snippet is None
    assert {claim.field for claim in result.field_provenance} == {
        "h_index",
        "current_affiliation",
        "has_contact",
    }
    assert not hasattr(result, "claimed_value")
    for claim in result.field_provenance:
        assert not hasattr(claim, "claimed_value")
    assert state.last_query == ""
    assert state.last_path.endswith(f"/v1/persons/{SEEDED_PERSON_ID}/evidence")
    assert state.request_count == 1


@pytest.mark.anyio
async def test_person_evidence_omits_rank_claims_when_ranks_are_absent(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person_evidence(
        SEEDED_PERSON_WITHOUT_RANKS_ID,
        request_id="req-evidence-2",
    )

    assert isinstance(result, PersonEvidenceFound)
    assert result.publications == SEEDED_PUBLICATIONS[SEEDED_PERSON_WITHOUT_RANKS_ID]
    assert result.field_provenance == SEEDED_FIELD_PROVENANCE[SEEDED_PERSON_WITHOUT_RANKS_ID]
    claimed_fields = {claim.field for claim in result.field_provenance}
    assert "qs_top200_rank" not in claimed_fields
    assert "world_top500_rank" not in claimed_fields


@pytest.mark.anyio
async def test_person_evidence_current_absence_is_not_an_empty_dossier(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.get_person_evidence(
        SEEDED_ABSENT_PERSON_ID,
        request_id="req-evidence-absent",
    )

    assert isinstance(result, PersonCurrentAbsence)
    assert result.outcome == "current_absence"
    assert result.canonical_person_id == SEEDED_ABSENT_PERSON_ID
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.request_id == "req-evidence-absent"
    assert not hasattr(result, "publications")
    assert not hasattr(result, "field_provenance")


@pytest.mark.anyio
async def test_person_detail_and_evidence_share_current_data_version(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    detail = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-same-dv-detail")
    evidence = await adapter.get_person_evidence(
        SEEDED_PERSON_ID,
        request_id="req-same-dv-evidence",
    )

    assert detail.data_version == evidence.data_version == DEFAULT_DATA_VERSION


@pytest.mark.anyio
async def test_blank_person_id_is_rejected_before_evidence_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_person_evidence("  ", request_id="req-blank-evidence")

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_person_evidence_auth_failure_is_not_retried(
    fake_client: httpx.AsyncClient,
) -> None:
    state.deny_auth = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=_noop_sleep)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence-auth")

    assert captured.value.category == "unauthenticated"
    assert captured.value.retryable is False
    assert captured.value.status_code == 401
    assert state.request_count == 1


@pytest.mark.anyio
async def test_person_evidence_unavailable_retries_then_fails(
    fake_client: httpx.AsyncClient,
) -> None:
    delays: list[float] = []

    async def sleeper(seconds: float) -> None:
        delays.append(seconds)

    state.status_5xx = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=sleeper)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence-5xx")

    assert captured.value.category == "unavailable"
    assert captured.value.retryable is True
    assert state.request_count == MAX_ATTEMPTS
    assert delays == [0.2, 0.4]


def _seeded_evidence_payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "outcome": "found",
        "request_id": "req-evidence",
        "data_version": DEFAULT_DATA_VERSION,
        "canonical_person_id": SEEDED_PERSON_ID,
        "publications": [
            item.model_dump(mode="json") for item in SEEDED_PUBLICATIONS[SEEDED_PERSON_ID]
        ],
        "field_provenance": [
            item.model_dump(mode="json") for item in SEEDED_FIELD_PROVENANCE[SEEDED_PERSON_ID]
        ],
    }
    body.update(overrides)
    return body


@pytest.mark.anyio
async def test_person_evidence_payload_with_email_is_invalid_and_not_retried() -> None:
    attempts = {"count": 0}
    payload = _seeded_evidence_payload()
    payload["email"] = "wei@example.com"

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False
    assert attempts["count"] == 1


@pytest.mark.anyio
async def test_person_evidence_missing_data_version_is_invalid_response() -> None:
    payload = _seeded_evidence_payload()
    del payload["data_version"]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_person_evidence_mismatched_request_id_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_seeded_evidence_payload(request_id="other-id"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_illegal_provenance_field_is_invalid_response() -> None:
    payload = _seeded_evidence_payload(
        field_provenance=[
            {
                "field": "email",
                "source_kind": "profile",
                "source_id": "src-orcid-001",
                "snippet": None,
            }
        ]
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_publication_provenance_must_reference_a_publication_in_the_payload() -> None:
    payload = _seeded_evidence_payload(
        field_provenance=[
            {
                "field": "h_index",
                "source_kind": "publication",
                "source_id": "pub-missing-001",
                "snippet": None,
            }
        ]
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.get_person_evidence(SEEDED_PERSON_ID, request_id="req-evidence")

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False
    assert SEEDED_PUBLICATION_ID != "pub-missing-001"


@pytest.mark.anyio
async def test_talent_search_returns_sorted_hits(fake_client: httpx.AsyncClient) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.search_talent(
        [HardCondition(field="chinese_identity", operator="eq", value="国内华人")],
        research_topic_query="人工智能",
        request_id="req-search-1",
    )

    assert isinstance(result, TalentSearchResponse)
    assert result.request_id == "req-search-1"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.person == SEEDED_PERSONS[SEEDED_PERSON_ID]
    assert hit.hit_publications == SEEDED_SEARCH_HIT_PUBLICATIONS[SEEDED_PERSON_ID]
    assert hit.hit_publications[0].title
    assert hit.hit_publications[0].year
    assert hit.hit_publications[0].venue
    assert hit.semantic_score == SEEDED_SEARCH_SEMANTIC_SCORES[SEEDED_PERSON_ID]
    assert hit.person.has_contact is True
    assert state.last_path == "/v1/search"
    assert state.request_count == 1


@pytest.mark.anyio
async def test_talent_search_empty_hard_conditions_allows_semantic_only_recall(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.search_talent(
        [],
        research_topic_query="人工智能",
        request_id="req-search-empty",
    )

    assert [hit.person.canonical_person_id for hit in result.hits] == [
        SEEDED_PERSON_WITHOUT_RANKS_ID,
        SEEDED_PERSON_ID,
    ]
    assert [hit.semantic_score for hit in result.hits] == [
        SEEDED_SEARCH_SEMANTIC_SCORES[SEEDED_PERSON_WITHOUT_RANKS_ID],
        SEEDED_SEARCH_SEMANTIC_SCORES[SEEDED_PERSON_ID],
    ]
    assert state.request_count == 1


@pytest.mark.parametrize("topic", ["", "   "])
@pytest.mark.anyio
async def test_talent_search_empty_query_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
    topic: str,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent([], research_topic_query=topic, request_id="req-blank")

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_talent_search_hard_filter_only_omits_semantic_scores(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.search_talent(
        [HardCondition(field="h_index", operator="gte", value=1)],
        request_id="req-hard-filter",
    )

    assert [hit.person.canonical_person_id for hit in result.hits] == [
        SEEDED_PERSON_ID,
        SEEDED_PERSON_WITHOUT_RANKS_ID,
    ]
    assert all(hit.semantic_score is None for hit in result.hits)
    assert result.hits[0].hit_publications == SEEDED_SEARCH_HIT_PUBLICATIONS[SEEDED_PERSON_ID]
    assert (
        result.hits[1].hit_publications
        == (SEEDED_SEARCH_HIT_PUBLICATIONS[SEEDED_PERSON_WITHOUT_RANKS_ID])
    )
    assert state.request_count == 1


@pytest.mark.anyio
async def test_talent_search_blank_topic_with_hard_conditions_is_hard_filter_only(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    result = await adapter.search_talent(
        [HardCondition(field="h_index", operator="gte", value=1)],
        research_topic_query="   ",
        request_id="req-hard-filter-blank",
    )

    assert [hit.person.canonical_person_id for hit in result.hits] == [
        SEEDED_PERSON_ID,
        SEEDED_PERSON_WITHOUT_RANKS_ID,
    ]
    assert all(hit.semantic_score is None for hit in result.hits)
    assert state.request_count == 1


@pytest.mark.parametrize("hit_limit", [0, 501])
@pytest.mark.anyio
async def test_talent_search_hit_limit_out_of_bounds_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
    hit_limit: int,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            hit_limit=hit_limit,
        )

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_talent_search_unknown_field_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent(
            [HardCondition(field="email", operator="eq", value="x")],
            research_topic_query="人工智能",
            request_id="req-unknown-field",
        )

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_talent_search_unknown_operator_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent(
            [HardCondition(field="h_index", operator="eq", value=30)],
            research_topic_query="人工智能",
            request_id="req-unknown-operator",
        )

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_talent_search_illegal_chinese_identity_is_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent(
            [HardCondition(field="chinese_identity", operator="eq", value="汉族")],
            research_topic_query="人工智能",
            request_id="req-illegal-identity",
        )

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 0


def test_talent_search_request_forbids_preference_and_unsupported_keys() -> None:
    with pytest.raises(ValidationError):
        _ = TalentSearchRequest.model_validate(
            {
                "hard_conditions": [],
                "research_topic_query": "人工智能",
                "preference_conditions": [{"field": "h_index", "operator": "gte", "value": 30}],
            }
        )
    with pytest.raises(ValidationError):
        _ = TalentSearchRequest.model_validate(
            {
                "hard_conditions": [],
                "research_topic_query": "人工智能",
                "unsupported_conditions": [{"description": "创业经验", "evidence": []}],
            }
        )
    with pytest.raises(ValidationError):
        _ = TalentSearchRequest.model_validate(
            {
                "hard_conditions": [],
                "research_topic_query": "人工智能",
                "search_utterance": "找清华大学的人",
            }
        )
    with pytest.raises(ValidationError):
        _ = TalentSearchRequest.model_validate(
            {
                "hard_conditions": [],
                "research_topic_query": "人工智能",
                "sort_by": "h_index",
            }
        )


def test_talent_search_request_allows_hard_filter_only_and_rejects_both_empty() -> None:
    request = TalentSearchRequest(
        hard_conditions=(HardCondition(field="h_index", operator="gte", value=10),)
    )
    assert request.research_topic_query == ""
    assert request.has_research_topic is False
    with pytest.raises(ValidationError):
        _ = TalentSearchRequest()


@pytest.mark.anyio
async def test_talent_search_forbidden_inputs_are_rejected_before_http(
    fake_client: httpx.AsyncClient,
) -> None:
    adapter = SearchBaseAdapter(_config(), client=fake_client)
    with pytest.raises(SearchBaseAdapterError) as preference_error:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            preference_conditions=[{"field": "h_index", "operator": "gte", "value": 30}],
        )
    with pytest.raises(SearchBaseAdapterError) as unsupported_error:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            unsupported_conditions=[{"description": "创业经验"}],
        )
    with pytest.raises(SearchBaseAdapterError) as utterance_error:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            search_utterance="找清华大学的人",
        )
    with pytest.raises(SearchBaseAdapterError) as job_text_error:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            job_description="招聘研究员",
        )
    with pytest.raises(SearchBaseAdapterError) as sort_error:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            sort_by="h_index",
        )

    for captured in (
        preference_error,
        unsupported_error,
        utterance_error,
        job_text_error,
        sort_error,
    ):
        assert captured.value.category == "invalid_query"
        assert captured.value.retryable is False
    assert state.request_count == 0


@pytest.mark.anyio
async def test_talent_search_invalid_query_from_provider_is_not_retried(
    fake_client: httpx.AsyncClient,
) -> None:
    state.invalid_query = True
    adapter = SearchBaseAdapter(_config(), client=fake_client, sleeper=_noop_sleep)
    with pytest.raises(SearchBaseAdapterError) as captured:
        _ = await adapter.search_talent(
            [],
            research_topic_query="人工智能",
            request_id="req-invalid-provider",
        )

    assert captured.value.category == "invalid_query"
    assert captured.value.retryable is False
    assert state.request_count == 1


@pytest.mark.anyio
async def test_talent_search_response_with_email_is_invalid_response() -> None:
    payload = {
        "request_id": "req-contact-search",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [
            {
                "person": SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json"),
                "hit_publications": [
                    SEEDED_SEARCH_HIT_PUBLICATIONS[SEEDED_PERSON_ID][0].model_dump(mode="json")
                ],
                "semantic_score": 0.91,
            }
        ],
        "email": "wei@example.com",
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-contact-search",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_response_misordered_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "req-order",
                "data_version": DEFAULT_DATA_VERSION,
                "hits": [
                    {
                        "person": SEEDED_PERSONS[SEEDED_PERSON_WITHOUT_RANKS_ID].model_dump(
                            mode="json"
                        ),
                        "hit_publications": [],
                        "semantic_score": 0.2,
                    },
                    {
                        "person": SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json"),
                        "hit_publications": [],
                        "semantic_score": 0.9,
                    },
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-order",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_response_non_finite_score_is_invalid_response() -> None:
    payload = {
        "request_id": "req-nan",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [
            {
                "person": SEEDED_PERSONS[SEEDED_PERSON_ID].model_dump(mode="json"),
                "hit_publications": [],
                "semantic_score": float("nan"),
            }
        ],
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-nan",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_response_missing_data_version_is_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"request_id": "req-missing-dv", "hits": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-missing-dv",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


def _search_hit_json(
    person_id: str,
    *,
    semantic_score: float | None = None,
    include_score: bool = True,
) -> dict[str, object]:
    body: dict[str, object] = {
        "person": SEEDED_PERSONS[person_id].model_dump(mode="json"),
        "hit_publications": [
            publication.model_dump(mode="json")
            for publication in SEEDED_SEARCH_HIT_PUBLICATIONS[person_id]
        ],
    }
    if include_score:
        body["semantic_score"] = semantic_score
    return body


@pytest.mark.anyio
async def test_talent_search_response_with_match_score_is_invalid_response() -> None:
    payload = {
        "request_id": "req-match-score",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [_search_hit_json(SEEDED_PERSON_ID, semantic_score=0.91)],
        "total_score": 12.5,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-match-score",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_hard_filter_response_with_score_is_invalid() -> None:
    payload = {
        "request_id": "req-hard-score",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [_search_hit_json(SEEDED_PERSON_ID, semantic_score=0)],
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [HardCondition(field="h_index", operator="gte", value=1)],
                request_id="req-hard-score",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_hard_filter_misordered_is_invalid_response() -> None:
    payload = {
        "request_id": "req-hard-order",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [
            _search_hit_json(SEEDED_PERSON_WITHOUT_RANKS_ID, include_score=False),
            _search_hit_json(SEEDED_PERSON_ID, include_score=False),
        ],
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [HardCondition(field="h_index", operator="gte", value=1)],
                request_id="req-hard-order",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False


@pytest.mark.anyio
async def test_talent_search_topic_response_missing_score_is_invalid() -> None:
    payload = {
        "request_id": "req-missing-score",
        "data_version": DEFAULT_DATA_VERSION,
        "hits": [_search_hit_json(SEEDED_PERSON_ID, include_score=False)],
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SearchBaseAdapter(_config(), client=client, sleeper=_noop_sleep)
        with pytest.raises(SearchBaseAdapterError) as captured:
            _ = await adapter.search_talent(
                [],
                research_topic_query="人工智能",
                request_id="req-missing-score",
            )

    assert captured.value.category == "invalid_response"
    assert captured.value.retryable is False
