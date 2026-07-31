from typing import Annotated, Self, final

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import mfa_service
from relationship_network_api.auth_service import (
    Authentication,
    AuthService,
    InvalidCredentialsError,
)
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    NOT_AUTHENTICATED_DETAIL,
    get_auth_service,
    get_db_session,
    get_settings,
    require_authentication,
)
from relationship_network_api.mfa_service import (
    INVALID_MFA_CODE_DETAIL,
    MFA_ALREADY_ENABLED_DETAIL,
    MFA_CHALLENGE_INVALID_DETAIL,
    MFA_NOT_ENABLED_DETAIL,
    MFA_REQUIRED_BY_TENANT_DETAIL,
    MFA_REQUIRED_FOR_PLATFORM_ADMIN_DETAIL,
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeInvalidError,
    MfaNotEnabledError,
    MfaRequiredByTenantError,
    MfaRequiredForPlatformAdminError,
)
from relationship_network_api.routers.auth import (
    AuthResponse,
    build_auth_response,
    set_session_cookie,
)

router = APIRouter()

_ONE_FACTOR_MESSAGE = "exactly one of code or recovery_code is required"

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AuthenticatedDep = Annotated[Authentication, Depends(require_authentication)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]


@final
class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


@final
class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@final
class MfaEnableResponse(BaseModel):
    recovery_codes: list[str]


@final
class MfaStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


@final
class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def _exactly_one_factor(self) -> Self:
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError(_ONE_FACTOR_MESSAGE)
        return self


@router.post("/auth/mfa/setup")
async def start_mfa_setup(
    authentication: AuthenticatedDep,
    session: DbSession,
) -> MfaSetupResponse:
    try:
        setup = await mfa_service.start_setup(session, user_id=authentication.user.id)
    except MfaAlreadyEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_ALREADY_ENABLED_DETAIL,
        ) from error
    except MfaNotEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from error
    return MfaSetupResponse(secret=setup.secret, otpauth_url=setup.otpauth_url)


@router.post("/auth/mfa/enable")
async def enable_mfa(
    payload: MfaCodeRequest,
    authentication: AuthenticatedDep,
    session: DbSession,
) -> MfaEnableResponse:
    try:
        codes = await mfa_service.enable(
            session,
            user_id=authentication.user.id,
            code=payload.code,
        )
    except MfaAlreadyEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_ALREADY_ENABLED_DETAIL,
        ) from error
    except MfaNotEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_NOT_ENABLED_DETAIL,
        ) from error
    except InvalidMfaCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_MFA_CODE_DETAIL,
        ) from error
    return MfaEnableResponse(recovery_codes=codes)


@router.post("/auth/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: MfaCodeRequest,
    authentication: AuthenticatedDep,
    session: DbSession,
) -> Response:
    try:
        await mfa_service.disable(session, user_id=authentication.user.id, code=payload.code)
    except MfaNotEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_NOT_ENABLED_DETAIL,
        ) from error
    except InvalidMfaCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_MFA_CODE_DETAIL,
        ) from error
    except MfaRequiredByTenantError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_REQUIRED_BY_TENANT_DETAIL,
        ) from error
    except MfaRequiredForPlatformAdminError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_REQUIRED_FOR_PLATFORM_ADMIN_DETAIL,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/mfa/status")
async def read_mfa_status(
    authentication: AuthenticatedDep,
    session: DbSession,
) -> MfaStatusResponse:
    try:
        mfa_status = await mfa_service.status(session, user_id=authentication.user.id)
    except MfaNotEnabledError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from error
    return MfaStatusResponse(
        enabled=mfa_status.enabled,
        recovery_codes_remaining=mfa_status.recovery_codes_remaining,
    )


@router.post("/auth/mfa/verify")
async def verify_mfa_challenge(
    payload: MfaVerifyRequest,
    response: Response,
    session: DbSession,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse:
    try:
        user = await mfa_service.complete_challenge(
            session,
            token=payload.mfa_token,
            code=payload.code,
            recovery_code=payload.recovery_code,
        )
    except MfaChallengeInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MFA_CHALLENGE_INVALID_DETAIL,
        ) from error
    except InvalidMfaCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_MFA_CODE_DETAIL,
        ) from error
    try:
        result = await service.complete_mfa_login(session, user=user)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MFA_CHALLENGE_INVALID_DETAIL,
        ) from error
    set_session_cookie(response, settings=settings, token=result.session.token)
    return build_auth_response(result.user, result.membership)
