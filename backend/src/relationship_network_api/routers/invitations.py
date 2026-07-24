import logging
import uuid
from datetime import datetime
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import invitation_service, tasks
from relationship_network_api.auth_service import Authentication
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    NOT_AUTHENTICATED_DETAIL,
    TenantContext,
    get_db_session,
    get_settings,
    require_authentication,
    require_permission,
)
from relationship_network_api.invitation_service import (
    ALREADY_IN_TENANT_DETAIL,
    EMAIL_ALREADY_MEMBER_DETAIL,
    INVITATION_ALREADY_ACCEPTED_DETAIL,
    INVITATION_ALREADY_PENDING_DETAIL,
    INVITATION_EMAIL_MISMATCH_DETAIL,
    INVITATION_INVALID_DETAIL,
    INVITATION_NOT_FOUND_DETAIL,
    AcceptedInvitation,
    AlreadyInTenantError,
    CreatedInvitation,
    EmailAlreadyMemberError,
    InvitationAlreadyAcceptedError,
    InvitationAlreadyPendingError,
    InvitationEmailMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    InvitationPreview,
    InvitationStatus,
    InvitationView,
    UserNotFoundError,
)
from relationship_network_api.models import MembershipRole

logger = logging.getLogger(__name__)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
MembersInviteDep = Annotated[TenantContext, Depends(require_permission("members:invite"))]
MembersReadDep = Annotated[TenantContext, Depends(require_permission("members:read"))]
AuthenticatedDep = Annotated[Authentication, Depends(require_authentication)]


@final
class InvitationCreateRequest(BaseModel):
    email: EmailStr = Field(max_length=320)


@final
class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


@final
class InvitationCreateResponse(BaseModel):
    invitation: InvitationResponse
    token: str
    invite_url: str


@final
class InvitationPreviewResponse(BaseModel):
    email: str
    tenant_name: str
    expires_at: datetime


@final
class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@final
class AcceptInvitationResponse(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: MembershipRole


def _invitation_response(invitation: InvitationView) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        created_at=invitation.created_at,
    )


def _invitation_invalid() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=INVITATION_INVALID_DETAIL,
    )


def _enqueue_invitation_email(*, email: str, tenant_name: str, invite_url: str) -> None:
    """Best-effort email delivery; a broker outage must never fail the request."""
    try:
        _ = tasks.send_invitation_email.delay(email, tenant_name, invite_url)
    except Exception:  # noqa: BLE001
        logger.warning("failed to enqueue invitation email", exc_info=True)


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InvitationCreateRequest,
    context: MembersInviteDep,
    session: DbSession,
    settings: SettingsDep,
) -> InvitationCreateResponse:
    try:
        created: CreatedInvitation = await invitation_service.create_invitation(
            session,
            tenant_id=context.tenant_id,
            email=payload.email,
            invited_by=context.authentication.user.id,
            invitation_ttl_seconds=settings.invitation_ttl_seconds,
        )
    except EmailAlreadyMemberError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=EMAIL_ALREADY_MEMBER_DETAIL,
        ) from error
    except InvitationAlreadyPendingError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=INVITATION_ALREADY_PENDING_DETAIL,
        ) from error
    invite_url = f"{settings.app_base_url}/invite/{created.token}"
    _enqueue_invitation_email(
        email=created.invitation.email,
        tenant_name=context.membership.tenant_name,
        invite_url=invite_url,
    )
    return InvitationCreateResponse(
        invitation=_invitation_response(created.invitation),
        token=created.token,
        invite_url=invite_url,
    )


@router.get("/invitations")
async def list_invitations(
    context: MembersReadDep,
    session: DbSession,
) -> list[InvitationResponse]:
    invitations = await invitation_service.list_invitations(session, tenant_id=context.tenant_id)
    return [_invitation_response(invitation) for invitation in invitations]


@router.post("/invitations/{invitation_id}/revoke")
async def revoke_invitation(
    invitation_id: uuid.UUID,
    context: MembersInviteDep,
    session: DbSession,
) -> InvitationResponse:
    try:
        invitation = await invitation_service.revoke_invitation(
            session,
            tenant_id=context.tenant_id,
            invitation_id=invitation_id,
        )
    except InvitationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=INVITATION_NOT_FOUND_DETAIL,
        ) from error
    except InvitationAlreadyAcceptedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=INVITATION_ALREADY_ACCEPTED_DETAIL,
        ) from error
    return _invitation_response(invitation)


@router.get("/invitations/preview")
async def preview_invitation(
    session: DbSession,
    token: Annotated[str, Query(min_length=1, max_length=200)],
) -> InvitationPreviewResponse:
    try:
        preview: InvitationPreview = await invitation_service.preview_invitation(
            session,
            token=token,
        )
    except InvitationInvalidError as error:
        raise _invitation_invalid() from error
    return InvitationPreviewResponse(
        email=preview.email,
        tenant_name=preview.tenant_name,
        expires_at=preview.expires_at,
    )


@router.post("/invitations/accept")
async def accept_invitation(
    payload: AcceptInvitationRequest,
    authentication: AuthenticatedDep,
    session: DbSession,
) -> AcceptInvitationResponse:
    try:
        user = await invitation_service.load_user(session, user_id=authentication.user.id)
        accepted: AcceptedInvitation = await invitation_service.accept_invitation(
            session,
            token=payload.token,
            user=user,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from error
    except InvitationInvalidError as error:
        raise _invitation_invalid() from error
    except InvitationEmailMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INVITATION_EMAIL_MISMATCH_DETAIL,
        ) from error
    except AlreadyInTenantError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ALREADY_IN_TENANT_DETAIL,
        ) from error
    return AcceptInvitationResponse(
        tenant_id=accepted.tenant_id,
        tenant_name=accepted.tenant_name,
        tenant_slug=accepted.tenant_slug,
        role=accepted.role,
    )
