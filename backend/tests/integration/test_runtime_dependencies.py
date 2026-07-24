import pytest

from relationship_network_api.config import load_app_settings
from relationship_network_api.health import evaluate_readiness
from relationship_network_api.probes import build_dependency_checks


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.integration
async def test_runtime_dependencies_are_ready() -> None:
    # Given the application receives the local deployment configuration
    checks = build_dependency_checks(load_app_settings())

    # When production dependency probes run against real services
    readiness = await evaluate_readiness(checks)

    # Then PostgreSQL, Redis, and object storage all report ready
    assert readiness.status == "ok"
    assert [dependency.status for dependency in readiness.dependencies] == ["ok", "ok", "ok"]
