import uuid
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from relationship_network_api.auth_service import Authentication
from relationship_network_api.deps import require_authentication
from relationship_network_api.membership_service import NO_ACTIVE_MEMBERSHIP_DETAIL
from relationship_network_api.models import MembershipRole

router = APIRouter()

AuthenticatedDep = Annotated[Authentication, Depends(require_authentication)]


@final
class CurrentTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: MembershipRole


@router.get("/tenants/current")
async def read_current_tenant(authentication: AuthenticatedDep) -> CurrentTenantResponse:
    membership = authentication.membership
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NO_ACTIVE_MEMBERSHIP_DETAIL,
        )
    return CurrentTenantResponse(
        id=membership.tenant_id,
        name=membership.tenant_name,
        slug=membership.tenant_slug,
        role=membership.role,
    )
