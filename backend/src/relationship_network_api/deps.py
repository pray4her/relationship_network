from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Final
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from relationship_network_api import rbac_service, tenant_context, usage_service
from relationship_network_api.auth_service import Authentication, AuthService, MembershipView
from relationship_network_api.config import (
    AppSettings,
    load_app_settings,
    parse_platform_admin_emails,
)
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.membership_service import NO_ACTIVE_MEMBERSHIP_DETAIL
from relationship_network_api.models import Tenant, User

SESSION_COOKIE_NAME: Final = "rn_session"
NOT_AUTHENTICATED_DETAIL: Final = "not_authenticated"
PERMISSION_DENIED_DETAIL: Final = "permission_denied"
MFA_REQUIRED_DETAIL: Final = "mfa_required"
PLATFORM_ADMIN_REQUIRED_DETAIL: Final = "platform_admin_required"
SUBSCRIPTION_READ_ONLY_DETAIL: Final = "subscription_read_only"


@dataclass(frozen=True)
class TenantContext:
    """Authenticated caller resolved into a tenant with effective permissions."""

    authentication: Authentication
    membership: MembershipView
    permissions: frozenset[str]

    @property
    def tenant_id(self) -> UUID:
        return self.membership.tenant_id


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
        mfa_challenge_ttl_seconds=settings.mfa_challenge_ttl_seconds,
        platform_admin_emails=parse_platform_admin_emails(settings.platform_admin_emails),
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


async def get_tenant_context(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    authentication: Annotated[Authentication, Depends(require_authentication)],
) -> TenantContext:
    """Resolve the tenant context and pin the database session to the tenant.

    Effective permissions are evaluated on every request, so role and
    permission changes take effect on the next request.
    """
    membership = authentication.membership
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NO_ACTIVE_MEMBERSHIP_DETAIL,
        )
    await tenant_context.set_tenant_context(session, membership.tenant_id)
    await _enforce_mfa_policy(
        session,
        tenant_id=membership.tenant_id,
        authentication=authentication,
    )
    permissions = await rbac_service.resolve_permissions(
        session,
        tenant_id=membership.tenant_id,
        membership_role=membership.role,
        membership_id=membership.membership_id,
    )
    return TenantContext(
        authentication=authentication,
        membership=membership,
        permissions=permissions,
    )


async def _enforce_mfa_policy(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    authentication: Authentication,
) -> None:
    """Reject members without MFA when the tenant enforces an MFA policy."""
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None or not tenant.mfa_required:
        return
    user = (
        await session.execute(select(User).where(User.id == authentication.user.id))
    ).scalar_one_or_none()
    if user is None or user.totp_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MFA_REQUIRED_DETAIL,
        )


def require_permission(
    permission: str,
) -> Callable[[TenantContext], Coroutine[object, object, TenantContext]]:
    """Build a dependency requiring a permission in the caller's tenant context."""

    async def dependency(
        context: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> TenantContext:
        if permission not in context.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=PERMISSION_DENIED_DETAIL,
            )
        return context

    return dependency


def require_writable_permission(
    permission: str,
) -> Callable[..., Coroutine[object, object, TenantContext]]:
    """Require both a permission and a writable (in-period) subscription."""
    permission_dependency = require_permission(permission)

    async def dependency(
        session: Annotated[AsyncSession, Depends(get_db_session)],
        context: Annotated[TenantContext, Depends(permission_dependency)],
    ) -> TenantContext:
        if not await usage_service.is_tenant_writable(
            session,
            tenant_id=context.membership.tenant_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=SUBSCRIPTION_READ_ONLY_DETAIL,
            )
        return context

    return dependency


async def require_writable_tenant(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    """Require the tenant's subscription to be in a writable (in-period) state.

    This gate is meant for business write endpoints (companies, jobs, matches,
    reports and the like): tenants whose paid period has lapsed keep read
    access but are rejected here. Offline order submission deliberately does
    not use this gate, because submitting an order is how an expired tenant
    resubscribes.
    """
    if not await usage_service.is_tenant_writable(
        session,
        tenant_id=context.membership.tenant_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUBSCRIPTION_READ_ONLY_DETAIL,
        )
    return context


WritableTenantDep = Annotated[TenantContext, Depends(require_writable_tenant)]


async def require_platform_admin(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    authentication: Annotated[Authentication, Depends(require_authentication)],
) -> Authentication:
    """Require a platform administrator who has enrolled MFA.

    Platform admin rights live outside tenant RBAC: tenant roles can never
    grant or derive them, and the management entry stays closed until the
    admin completes TOTP enrollment.
    """
    user = (
        await session.execute(select(User).where(User.id == authentication.user.id))
    ).scalar_one_or_none()
    if user is None or not user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PLATFORM_ADMIN_REQUIRED_DETAIL,
        )
    if user.totp_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MFA_REQUIRED_DETAIL,
        )
    return authentication
