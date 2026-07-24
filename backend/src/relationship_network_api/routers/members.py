import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import membership_service, rbac_service, tenant_context
from relationship_network_api.deps import TenantContext, get_db_session, require_permission
from relationship_network_api.invitation_service import (
    ALREADY_IN_TENANT_DETAIL,
    AlreadyInTenantError,
)
from relationship_network_api.membership_service import (
    MEMBERSHIP_NOT_FOUND_DETAIL,
    PROTECTED_OWNER_DETAIL,
    MembershipNotFoundError,
    ProtectedOwnerError,
)
from relationship_network_api.routers.rbac import MemberResponse, member_response

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MembersManageDep = Annotated[TenantContext, Depends(require_permission("members:manage"))]


async def _reload_member(
    session: AsyncSession,
    *,
    context: TenantContext,
    membership_id: uuid.UUID,
) -> MemberResponse:
    # The service committed, ending the transaction-local tenant context;
    # re-pin it before reading the updated membership back.
    await tenant_context.set_tenant_context(session, context.tenant_id)
    members = await rbac_service.list_members(session, tenant_id=context.tenant_id)
    return member_response(
        next(member for member in members if member.membership_id == membership_id)
    )


@router.post("/members/{membership_id}/deactivate")
async def deactivate_membership(
    membership_id: uuid.UUID,
    context: MembersManageDep,
    session: DbSession,
) -> MemberResponse:
    try:
        await membership_service.deactivate_membership(
            session,
            tenant_id=context.tenant_id,
            membership_id=membership_id,
        )
    except MembershipNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MEMBERSHIP_NOT_FOUND_DETAIL,
        ) from error
    except ProtectedOwnerError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PROTECTED_OWNER_DETAIL,
        ) from error
    return await _reload_member(session, context=context, membership_id=membership_id)


@router.post("/members/{membership_id}/activate")
async def activate_membership(
    membership_id: uuid.UUID,
    context: MembersManageDep,
    session: DbSession,
) -> MemberResponse:
    try:
        await membership_service.activate_membership(
            session,
            tenant_id=context.tenant_id,
            membership_id=membership_id,
        )
    except MembershipNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MEMBERSHIP_NOT_FOUND_DETAIL,
        ) from error
    except AlreadyInTenantError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ALREADY_IN_TENANT_DETAIL,
        ) from error
    return await _reload_member(session, context=context, membership_id=membership_id)


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_membership(
    membership_id: uuid.UUID,
    context: MembersManageDep,
    session: DbSession,
) -> Response:
    try:
        await membership_service.remove_membership(
            session,
            tenant_id=context.tenant_id,
            membership_id=membership_id,
        )
    except MembershipNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MEMBERSHIP_NOT_FOUND_DETAIL,
        ) from error
    except ProtectedOwnerError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PROTECTED_OWNER_DETAIL,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
