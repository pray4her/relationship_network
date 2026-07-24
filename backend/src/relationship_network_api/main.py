from collections.abc import Sequence

from fastapi import FastAPI, Response, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relationship_network_api.config import AppSettings, load_app_settings
from relationship_network_api.health import (
    DependencyCheck,
    LiveStatus,
    ReadinessStatus,
    evaluate_readiness,
)
from relationship_network_api.probes import build_dependency_checks
from relationship_network_api.routers.auth import router as auth_router
from relationship_network_api.routers.tenants import router as tenants_router


def create_app(
    *,
    checks: Sequence[DependencyCheck] | None = None,
    settings: AppSettings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    resolved_checks = build_dependency_checks(load_app_settings()) if checks is None else checks
    app = FastAPI(
        title="Relationship Network API",
        version="0.1.0",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.include_router(auth_router)
    app.include_router(tenants_router)

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
