import uuid
from datetime import datetime
from typing import Annotated, Final, Literal, final

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import invitation_service, rbac_service, tenant_context
from relationship_network_api.auth_service import (
    Authentication,
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    MembershipView,
    MfaPending,
    UserView,
)
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_auth_service,
    get_db_session,
    get_settings,
    require_authentication,
)
from relationship_network_api.membership_service import NO_ACTIVE_MEMBERSHIP_DETAIL
from relationship_network_api.models import MembershipRole

DUPLICATE_EMAIL_DETAIL: Final = "email_already_registered"
INVALID_CREDENTIALS_DETAIL: Final = "invalid_credentials"

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
AuthenticatedDep = Annotated[Authentication, Depends(require_authentication)]


@final
class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=50)
    tenant_name: str | None = Field(default=None, min_length=1, max_length=100)
    invite_token: str | None = Field(default=None, min_length=1, max_length=200)


@final
class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)


@final
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool


@final
class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


@final
class AuthResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse | None
    role: MembershipRole | None


@final
class MeResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse | None
    role: MembershipRole | None
    permissions: list[str]


@final
class MfaRequiredResponse(BaseModel):
    mfa_required: Literal[True] = True
    mfa_token: str
    expires_at: datetime


def build_auth_response(user: UserView, membership: MembershipView | None) -> AuthResponse:
    """Render the pinned registration/login/me response shape.

    Platform administrators without a tenant membership get null tenant and
    role; they hold no tenant permissions.
    """
    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_platform_admin=user.is_platform_admin,
        ),
        tenant=(
            TenantResponse(
                id=membership.tenant_id,
                name=membership.tenant_name,
                slug=membership.tenant_slug,
            )
            if membership is not None
            else None
        ),
        role=membership.role if membership is not None else None,
    )


def set_session_cookie(response: Response, *, settings: AppSettings, token: str) -> None:
    """Attach the opaque session cookie with the pinned attributes."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_ttl_seconds,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: DbSession,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse:
    try:
        result = await service.register(
            session,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            tenant_name=payload.tenant_name,
            invite_token=payload.invite_token,
        )
    except DuplicateEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
        ) from error
    except invitation_service.InvitationInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=invitation_service.INVITATION_INVALID_DETAIL,
        ) from error
    except invitation_service.InvitationEmailMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=invitation_service.INVITATION_EMAIL_MISMATCH_DETAIL,
        ) from error
    set_session_cookie(response, settings=settings, token=result.session.token)
    return build_auth_response(result.user, result.membership)


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    response: Response,
    session: DbSession,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse | MfaRequiredResponse:
    try:
        result = await service.login(session, email=payload.email, password=payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_DETAIL,
        ) from error
    if isinstance(result, MfaPending):
        return MfaRequiredResponse(mfa_token=result.mfa_token, expires_at=result.expires_at)
    set_session_cookie(response, settings=settings, token=result.session.token)
    return build_auth_response(result.user, result.membership)


@router.post("/auth/logout")
async def logout(
    request: Request,
    session: DbSession,
    service: AuthServiceDep,
) -> Response:
    await service.logout(session, token=request.cookies.get(SESSION_COOKIE_NAME))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/auth/me")
async def read_current_identity(
    request: Request,
    response: Response,
    authentication: AuthenticatedDep,
    session: DbSession,
    settings: SettingsDep,
) -> MeResponse:
    membership = authentication.membership
    if membership is None and not authentication.user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NO_ACTIVE_MEMBERSHIP_DETAIL,
        )
    if authentication.renewed:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            set_session_cookie(response, settings=settings, token=token)
    permissions: frozenset[str] = frozenset()
    if membership is not None:
        # The authenticate call committed, ending the transaction-local tenant
        # context; re-pin it before resolving permissions from RLS-scoped tables.
        await tenant_context.set_tenant_context(session, membership.tenant_id)
        permissions = await rbac_service.resolve_permissions(
            session,
            tenant_id=membership.tenant_id,
            membership_role=membership.role,
            membership_id=membership.membership_id,
        )
    auth_response = build_auth_response(authentication.user, membership)
    return MeResponse(**auth_response.model_dump(), permissions=sorted(permissions))
