from typing import final

import pytest
from anyio import Event, Lock, fail_after

from relationship_network_api.health import (
    DependencyName,
    DependencyProbeError,
    DependencyStatus,
    evaluate_readiness,
)


@final
class CoordinatedDependencyCheck:
    name: DependencyName

    def __init__(self, name: DependencyName, coordinator: "StartCoordinator") -> None:
        self.name = name
        self._coordinator = coordinator

    async def check(self) -> DependencyStatus:
        await self._coordinator.arrive()
        return DependencyStatus.model_validate({"name": self.name, "status": "ok"})


@final
class StartCoordinator:
    def __init__(self, expected: int) -> None:
        self._arrivals = 0
        self._expected = expected
        self._lock = Lock()
        self._all_started = Event()

    async def arrive(self) -> None:
        async with self._lock:
            self._arrivals += 1
            if self._arrivals == self._expected:
                self._all_started.set()
        await self._all_started.wait()


@final
class FailingDependencyCheck:
    name: DependencyName = "redis"

    async def check(self) -> DependencyStatus:
        message = "unexpected probe failure"
        raise DependencyProbeError(message)


@pytest.mark.anyio
async def test_dependency_checks_run_concurrently() -> None:
    coordinator = StartCoordinator(expected=3)

    with fail_after(1):
        result = await evaluate_readiness(
            (
                CoordinatedDependencyCheck("postgres", coordinator),
                CoordinatedDependencyCheck("redis", coordinator),
                CoordinatedDependencyCheck("object_storage", coordinator),
            )
        )

    assert result.status == "ok"


@pytest.mark.anyio
async def test_expected_probe_error_degrades_only_that_dependency() -> None:
    result = await evaluate_readiness((FailingDependencyCheck(),))

    assert result.model_dump() == {
        "dependencies": ({"name": "redis", "status": "unavailable"},),
        "status": "degraded",
    }
