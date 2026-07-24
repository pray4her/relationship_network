import uuid
from typing import Annotated, Final, final

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.auth_service import (
    Authentication,
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    MembershipView,
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


@final
class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)


@final
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str


@final
class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


@final
class AuthResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    role: MembershipRole


def build_auth_response(user: UserView, membership: MembershipView) -> AuthResponse:
    """Render the pinned registration/login/me response shape."""
    return AuthResponse(
        user=UserResponse(id=user.id, email=user.email, display_name=user.display_name),
        tenant=TenantResponse(
            id=membership.tenant_id,
            name=membership.tenant_name,
            slug=membership.tenant_slug,
        ),
        role=membership.role,
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
        )
    except DuplicateEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EMAIL_DETAIL,
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
) -> AuthResponse:
    try:
        result = await service.login(session, email=payload.email, password=payload.password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_DETAIL,
        ) from error
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
    settings: SettingsDep,
) -> AuthResponse:
    membership = authentication.membership
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NO_ACTIVE_MEMBERSHIP_DETAIL,
        )
    if authentication.renewed:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            set_session_cookie(response, settings=settings, token=token)
    return build_auth_response(authentication.user, membership)
