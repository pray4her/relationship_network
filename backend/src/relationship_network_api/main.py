from collections.abc import Sequence

from fastapi import FastAPI, Response, status

from relationship_network_api.config import load_app_settings
from relationship_network_api.health import (
    DependencyCheck,
    LiveStatus,
    ReadinessStatus,
    evaluate_readiness,
)
from relationship_network_api.probes import build_dependency_checks


def create_app(*, checks: Sequence[DependencyCheck] | None = None) -> FastAPI:
    resolved_checks = build_dependency_checks(load_app_settings()) if checks is None else checks
    app = FastAPI(
        title="Relationship Network API",
        version="0.1.0",
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> LiveStatus:
        return LiveStatus()

    @app.get("/health/ready", tags=["health"])
    async def readiness(response: Response) -> ReadinessStatus:
        result = await evaluate_readiness(resolved_checks)
        if result.status == "degraded":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result

    return app
