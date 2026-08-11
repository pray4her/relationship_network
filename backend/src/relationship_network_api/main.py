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
from relationship_network_api.routers.admin import router as admin_router
from relationship_network_api.routers.auth import router as auth_router
from relationship_network_api.routers.billing import router as billing_router
from relationship_network_api.routers.companies import router as companies_router
from relationship_network_api.routers.invitations import router as invitations_router
from relationship_network_api.routers.job_requirements import router as job_requirements_router
from relationship_network_api.routers.jobs import router as jobs_router
from relationship_network_api.routers.llm_calls import router as llm_calls_router
from relationship_network_api.routers.llm_configuration import router as llm_configuration_router
from relationship_network_api.routers.members import router as members_router
from relationship_network_api.routers.mfa import router as mfa_router
from relationship_network_api.routers.rbac import router as rbac_router
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
    app.include_router(rbac_router)
    app.include_router(invitations_router)
    app.include_router(members_router)
    app.include_router(companies_router)
    app.include_router(jobs_router)
    app.include_router(job_requirements_router)
    app.include_router(mfa_router)
    app.include_router(admin_router)
    app.include_router(llm_configuration_router)
    app.include_router(llm_calls_router)
    app.include_router(billing_router)

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
