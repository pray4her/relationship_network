from collections.abc import Sequence
from typing import final

from fastapi.testclient import TestClient

from relationship_network_api.health import DependencyCheck, DependencyName, DependencyStatus
from relationship_network_api.main import create_app


@final
class FixedDependencyCheck:
    name: DependencyName

    def __init__(self, result: DependencyStatus) -> None:
        self.name = result.name
        self._result = result

    async def check(self) -> DependencyStatus:
        return self._result


def make_client(results: Sequence[DependencyStatus]) -> TestClient:
    checks: tuple[DependencyCheck, ...] = tuple(FixedDependencyCheck(result) for result in results)
    return TestClient(create_app(checks=checks))


def test_liveness_reports_running_service() -> None:
    # Given a running API process
    client = make_client(())

    # When liveness is requested
    response = client.get("/health/live")

    # Then the public contract reports the service as alive
    assert response.status_code == 200
    assert response.json() == {
        "service": "relationship-network-api",
        "status": "ok",
    }


def test_readiness_reports_all_dependencies() -> None:
    # Given every required dependency is available
    client = make_client(
        (
            DependencyStatus(name="postgres", status="ok"),
            DependencyStatus(name="redis", status="ok"),
            DependencyStatus(name="object_storage", status="ok"),
        )
    )

    # When readiness is requested
    response = client.get("/health/ready")

    # Then the API exposes each successful dependency
    assert response.status_code == 200
    assert response.json() == {
        "dependencies": [
            {"name": "postgres", "status": "ok"},
            {"name": "redis", "status": "ok"},
            {"name": "object_storage", "status": "ok"},
        ],
        "status": "ok",
    }


def test_readiness_returns_service_unavailable_for_failed_dependency() -> None:
    # Given one required dependency is unavailable
    client = make_client(
        (
            DependencyStatus(name="postgres", status="ok"),
            DependencyStatus(name="redis", status="unavailable"),
        )
    )

    # When readiness is requested
    response = client.get("/health/ready")

    # Then callers receive a degraded contract and an actionable HTTP status
    assert response.status_code == 503
    assert response.json() == {
        "dependencies": [
            {"name": "postgres", "status": "ok"},
            {"name": "redis", "status": "unavailable"},
        ],
        "status": "degraded",
    }
