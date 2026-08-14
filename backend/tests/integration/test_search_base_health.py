import pytest

from relationship_network_api.fake_search_base import DEFAULT_DATA_VERSION, DEFAULT_SERVICE_API_KEY
from relationship_network_api.search_base import SearchBaseAdapter, SearchBaseClientConfig
from relationship_network_api.search_base_contract import (
    EXECUTABLE_SCHEMA_VERSIONS,
    SEARCH_CONTRACT_VERSION_V1,
)


@pytest.mark.integration
@pytest.mark.anyio
async def test_adapter_health_over_real_http(fake_search_base_base_url: str) -> None:
    adapter = SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=DEFAULT_SERVICE_API_KEY,
            base_url=fake_search_base_base_url,
            timeout_seconds=3,
        )
    )

    result = await adapter.check_health(request_id="req-http-1")

    assert result.request_id == "req-http-1"
    assert result.contract_version == SEARCH_CONTRACT_VERSION_V1
    assert result.executable_schema_versions == EXECUTABLE_SCHEMA_VERSIONS
    assert result.data_version == DEFAULT_DATA_VERSION
    assert result.status == "ok"
