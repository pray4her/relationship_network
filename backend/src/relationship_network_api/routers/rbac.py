import uuid
from typing import Annotated, final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import rbac_service, tenant_context
from relationship_network_api.deps import TenantContext, get_db_session, require_permission
from relationship_network_api.rbac_service import (
    DUPLICATE_ROLE_NAME_DETAIL,
    MEMBERSHIP_NOT_FOUND_DETAIL,
    ROLE_NOT_FOUND_DETAIL,
    SYSTEM_PERMISSIONS,
    UNKNOWN_PERMISSION_DETAIL,
    DuplicateRoleNameError,
    MembershipNotFoundError,
    MemberView,
    RoleNotFoundError,
    RoleView,
    UnknownPermissionError,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RolesReadDep = Annotated[TenantContext, Depends(require_permission("roles:read"))]
RolesManageDep = Annotated[TenantContext, Depends(require_permission("roles:manage"))]
MembersReadDep = Annotated[TenantContext, Depends(require_permission("members:read"))]
MembersManageDep = Annotated[TenantContext, Depends(require_permission("members:manage"))]


@final
class PermissionEntry(BaseModel):
    code: str
    description: str


@final
class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)
    permissions: list[str] = Field(default_factory=list)


@final
class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    permissions: list[str] | None = None
    is_active: bool | None = None


@final
class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    is_active: bool
    permissions: list[str]


@final
class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    membership_role: str
    is_active: bool
    role_ids: list[uuid.UUID]


@final
class AssignRolesRequest(BaseModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list)


def _role_response(role: RoleView) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_active=role.is_active,
        permissions=sorted(role.permissions),
    )


def _member_response(member: MemberView) -> MemberResponse:
    return MemberResponse(
        membership_id=member.membership_id,
        user_id=member.user_id,
        email=member.email,
        display_name=member.display_name,
        membership_role=member.membership_role,
        is_active=member.is_active,
        role_ids=sorted(member.role_ids),
    )


def _unknown_permission() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=UNKNOWN_PERMISSION_DETAIL,
    )


@router.get("/permissions")
async def list_permissions(_context: RolesReadDep) -> list[PermissionEntry]:
    return [
        PermissionEntry(code=code, description=description)
        for code, description in sorted(SYSTEM_PERMISSIONS.items())
    ]


@router.get("/roles")
async def list_roles(context: RolesReadDep, session: DbSession) -> list[RoleResponse]:
    roles = await rbac_service.list_roles(session, tenant_id=context.tenant_id)
    return [_role_response(role) for role in roles]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    context: RolesManageDep,
    session: DbSession,
) -> RoleResponse:
    try:
        role = await rbac_service.create_role(
            session,
            tenant_id=context.tenant_id,
            name=payload.name,
            description=payload.description,
            permissions=payload.permissions,
        )
    except UnknownPermissionError as error:
        raise _unknown_permission() from error
    except DuplicateRoleNameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_ROLE_NAME_DETAIL,
        ) from error
    return _role_response(role)


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    context: RolesManageDep,
    session: DbSession,
) -> RoleResponse:
    try:
        role = await rbac_service.update_role(
            session,
            tenant_id=context.tenant_id,
            role_id=role_id,
            name=payload.name,
            description=payload.description,
            permissions=payload.permissions,
            is_active=payload.is_active,
        )
    except RoleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ROLE_NOT_FOUND_DETAIL,
        ) from error
    except UnknownPermissionError as error:
        raise _unknown_permission() from error
    except DuplicateRoleNameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_ROLE_NAME_DETAIL,
        ) from error
    return _role_response(role)


@router.get("/members")
async def list_members(context: MembersReadDep, session: DbSession) -> list[MemberResponse]:
    members = await rbac_service.list_members(session, tenant_id=context.tenant_id)
    return [_member_response(member) for member in members]


@router.put("/members/{membership_id}/roles")
async def assign_roles(
    membership_id: uuid.UUID,
    payload: AssignRolesRequest,
    context: MembersManageDep,
    session: DbSession,
) -> MemberResponse:
    try:
        await rbac_service.assign_roles(
            session,
            tenant_id=context.tenant_id,
            membership_id=membership_id,
            role_ids=payload.role_ids,
        )
    except MembershipNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MEMBERSHIP_NOT_FOUND_DETAIL,
        ) from error
    except RoleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ROLE_NOT_FOUND_DETAIL,
        ) from error
    # The service committed, ending the transaction-local tenant context;
    # re-pin it before reading the updated membership back.
    await tenant_context.set_tenant_context(session, context.tenant_id)
    members = await rbac_service.list_members(session, tenant_id=context.tenant_id)
    return _member_response(
        next(member for member in members if member.membership_id == membership_id)
    )
