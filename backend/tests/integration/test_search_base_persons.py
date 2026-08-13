import pytest

from relationship_network_api.fake_search_base import (
    DEFAULT_DATA_VERSION,
    DEFAULT_SERVICE_API_KEY,
    SEEDED_ABSENT_PERSON_ID,
    SEEDED_FIELD_PROVENANCE,
    SEEDED_PERSON_ID,
    SEEDED_PERSONS,
    SEEDED_PUBLICATIONS,
)
from relationship_network_api.search_base import SearchBaseAdapter, SearchBaseClientConfig
from relationship_network_api.search_base_contract import (
    PersonCurrentAbsence,
    PersonDetailFound,
    PersonEvidenceFound,
)


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_person_detail_over_real_http(fake_search_base_base_url: str) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    result = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-http-person")

    assert isinstance(result, PersonDetailFound)
    assert result.request_id == "req-http-person"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.person == SEEDED_PERSONS[SEEDED_PERSON_ID]


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_person_batch_current_absence_over_real_http(
    fake_search_base_base_url: str,
) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    result = await adapter.get_persons(
        [SEEDED_PERSON_ID, SEEDED_ABSENT_PERSON_ID],
        request_id="req-http-batch",
    )

    assert result.request_id == "req-http-batch"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.persons == (SEEDED_PERSONS[SEEDED_PERSON_ID],)
    assert result.currently_absent_ids == (SEEDED_ABSENT_PERSON_ID,)

    detail = await adapter.get_person(SEEDED_ABSENT_PERSON_ID, request_id="req-http-absent")
    assert isinstance(detail, PersonCurrentAbsence)
    assert detail.canonical_person_id == SEEDED_ABSENT_PERSON_ID


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_person_evidence_over_real_http(fake_search_base_base_url: str) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    evidence = await adapter.get_person_evidence(
        SEEDED_PERSON_ID,
        request_id="req-http-evidence",
    )
    detail = await adapter.get_person(SEEDED_PERSON_ID, request_id="req-http-evidence-detail")

    assert isinstance(evidence, PersonEvidenceFound)
    assert evidence.request_id == "req-http-evidence"
    assert evidence.data_version == DEFAULT_DATA_VERSION
    assert evidence.publications == SEEDED_PUBLICATIONS[SEEDED_PERSON_ID]
    assert evidence.field_provenance == SEEDED_FIELD_PROVENANCE[SEEDED_PERSON_ID]
    assert evidence.data_version == detail.data_version

    absent = await adapter.get_person_evidence(
        SEEDED_ABSENT_PERSON_ID,
        request_id="req-http-evidence-absent",
    )
    assert isinstance(absent, PersonCurrentAbsence)
    assert absent.canonical_person_id == SEEDED_ABSENT_PERSON_ID
    assert absent.data_version == DEFAULT_DATA_VERSION
