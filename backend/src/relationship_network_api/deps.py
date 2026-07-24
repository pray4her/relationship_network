from collections.abc import AsyncIterator
from typing import Annotated, Final

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from relationship_network_api.auth_service import Authentication, AuthService
from relationship_network_api.config import AppSettings, load_app_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory

SESSION_COOKIE_NAME: Final = "rn_session"
NOT_AUTHENTICATED_DETAIL: Final = "not_authenticated"


def get_settings(request: Request) -> AppSettings:
    """Resolve application settings, loading them lazily on first use."""
    settings = request.app.state.settings
    if settings is None:
        settings = load_app_settings()
        request.app.state.settings = settings
    return settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session from the shared factory."""
    session_factory = request.app.state.session_factory
    if session_factory is None:
        engine: AsyncEngine = create_engine_from_settings(get_settings(request))
        session_factory = create_session_factory(engine)
        request.app.state.engine = engine
        request.app.state.session_factory = session_factory
    async with session_factory() as session:
        yield session


def get_auth_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AuthService:
    """Build the auth service from application settings."""
    return AuthService(
        session_ttl_seconds=settings.session_ttl_seconds,
        session_renewal_window_seconds=settings.session_renewal_window_seconds,
    )


async def get_authentication(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Authentication | None:
    """Resolve the caller identity from the session cookie, or None when anonymous."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return await service.authenticate(session, token=token)


def require_authentication(
    authentication: Annotated[Authentication | None, Depends(get_authentication)],
) -> Authentication:
    """Require an authenticated caller, rejecting anonymous requests with 401."""
    if authentication is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        )
    return authentication
