import pytest

from relationship_network_api.fake_search_base import (
    DEFAULT_DATA_VERSION,
    DEFAULT_SERVICE_API_KEY,
    SEEDED_PERSON_ID,
    SEEDED_PERSON_WITHOUT_RANKS_ID,
    SEEDED_PERSONS,
    SEEDED_SEARCH_HIT_PUBLICATIONS,
    SEEDED_SEARCH_SEMANTIC_SCORES,
)
from relationship_network_api.search_base import SearchBaseAdapter, SearchBaseClientConfig
from relationship_network_api.search_base_contract import HardCondition, TalentSearchResponse


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_talent_search_over_real_http(fake_search_base_base_url: str) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    result = await adapter.search_talent(
        [HardCondition(field="chinese_identity", operator="eq", value="国内华人")],
        research_topic_query="人工智能",
        request_id="req-http-search",
    )

    assert isinstance(result, TalentSearchResponse)
    assert result.request_id == "req-http-search"
    assert result.data_version == DEFAULT_DATA_VERSION
    assert len(result.hits) == 1
    assert result.hits[0].person == SEEDED_PERSONS[SEEDED_PERSON_ID]
    assert result.hits[0].hit_publications == SEEDED_SEARCH_HIT_PUBLICATIONS[SEEDED_PERSON_ID]
    assert result.hits[0].semantic_score == SEEDED_SEARCH_SEMANTIC_SCORES[SEEDED_PERSON_ID]


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_hard_filter_only_search_over_real_http(
    fake_search_base_base_url: str,
) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    result = await adapter.search_talent(
        [HardCondition(field="h_index", operator="gte", value=1)],
        request_id="req-http-hard-filter",
    )

    assert isinstance(result, TalentSearchResponse)
    assert result.request_id == "req-http-hard-filter"
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
