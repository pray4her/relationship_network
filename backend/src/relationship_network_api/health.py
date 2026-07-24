from collections.abc import Sequence
from typing import ClassVar, Literal, Protocol, final

from anyio import create_task_group
from pydantic import BaseModel, ConfigDict

type DependencyName = Literal["postgres", "redis", "object_storage"]
type DependencyState = Literal["ok", "unavailable"]
type ReadinessState = Literal["ok", "degraded"]


class DependencyProbeError(Exception):
    pass


@final
class DependencyStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: DependencyName
    status: DependencyState


class DependencyCheck(Protocol):
    @property
    def name(self) -> DependencyName: ...

    async def check(self) -> DependencyStatus: ...


@final
class LiveStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    service: Literal["relationship-network-api"] = "relationship-network-api"
    status: Literal["ok"] = "ok"


@final
class ReadinessStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    dependencies: tuple[DependencyStatus, ...]
    status: ReadinessState


async def evaluate_readiness(checks: Sequence[DependencyCheck]) -> ReadinessStatus:
    results: dict[int, DependencyStatus] = {}

    async def run_check(index: int, check: DependencyCheck) -> None:
        try:
            results[index] = await check.check()
        except DependencyProbeError:
            results[index] = DependencyStatus(name=check.name, status="unavailable")

    async with create_task_group() as task_group:
        for index, check in enumerate(checks):
            _ = task_group.start_soon(run_check, index, check)

    dependencies = tuple(results[index] for index in range(len(checks)))
    status: ReadinessState = (
        "ok" if all(dependency.status == "ok" for dependency in dependencies) else "degraded"
    )
    return ReadinessStatus(dependencies=dependencies, status=status)
