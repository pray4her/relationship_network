import uuid
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import mfa_service
from relationship_network_api.deps import (
    TenantContext,
    get_db_session,
    get_tenant_context,
    require_permission,
)
from relationship_network_api.mfa_service import (
    MFA_SETUP_REQUIRED_DETAIL,
    TENANT_NOT_FOUND_DETAIL,
    MfaSetupRequiredError,
    TenantNotFoundError,
)
from relationship_network_api.models import MembershipRole

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentTenantDep = Annotated[TenantContext, Depends(get_tenant_context)]
TenantManageDep = Annotated[TenantContext, Depends(require_permission("tenant:manage"))]


@final
class CurrentTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: MembershipRole


@final
class MfaPolicyRequest(BaseModel):
    required: bool


@final
class TenantMfaPolicyResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    mfa_required: bool


@router.get("/tenants/current")
async def read_current_tenant(context: CurrentTenantDep) -> CurrentTenantResponse:
    membership = context.membership
    return CurrentTenantResponse(
        id=membership.tenant_id,
        name=membership.tenant_name,
        slug=membership.tenant_slug,
        role=membership.role,
    )


@router.put("/tenants/current/mfa-policy")
async def update_mfa_policy(
    payload: MfaPolicyRequest,
    context: TenantManageDep,
    session: DbSession,
) -> TenantMfaPolicyResponse:
    try:
        view = await mfa_service.set_tenant_mfa_policy(
            session,
            tenant_id=context.tenant_id,
            user_id=context.authentication.user.id,
            required=payload.required,
        )
    except MfaSetupRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MFA_SETUP_REQUIRED_DETAIL,
        ) from error
    except TenantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TENANT_NOT_FOUND_DETAIL,
        ) from error
    return TenantMfaPolicyResponse(
        id=view.id,
        name=view.name,
        slug=view.slug,
        mfa_required=view.mfa_required,
    )
