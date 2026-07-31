import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final, final

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.models import (
    OWNER_ROLE,
    MembershipRole,
    MembershipRoleAssignment,
    Role,
    RolePermission,
    TenantMembership,
    User,
)

SYSTEM_PERMISSIONS: Final[dict[str, str]] = {
    "roles:read": "查看角色与权限目录",
    "roles:manage": "创建、编辑与停用角色",
    "members:read": "查看租户成员及其角色",
    "members:manage": "为租户成员分配角色",
    "members:invite": "邀请新成员加入租户",
    "tenant:manage": "管理租户设置",
    "billing:read": "查看套餐权益与用量",
}
"""System-defined permission catalog; codes are stable and assigned to roles."""

UNKNOWN_PERMISSION_DETAIL: Final = "unknown_permission"
DUPLICATE_ROLE_NAME_DETAIL: Final = "duplicate_role_name"
ROLE_NOT_FOUND_DETAIL: Final = "role_not_found"
MEMBERSHIP_NOT_FOUND_DETAIL: Final = "membership_not_found"


@final
class UnknownPermissionError(Exception):
    """Raised when a permission code is not part of the system catalog."""

    def __init__(self, codes: frozenset[str]) -> None:
        super().__init__(", ".join(sorted(codes)))
        self.codes = codes


@final
class DuplicateRoleNameError(Exception):
    """Raised when a role name is already used within the tenant."""


@final
class RoleNotFoundError(Exception):
    """Raised when a role does not exist in the caller's tenant."""


@final
class MembershipNotFoundError(Exception):
    """Raised when a membership does not exist in the caller's tenant."""


@final
@dataclass(frozen=True)
class RoleView:
    """A tenant role with the permissions granted to it."""

    id: uuid.UUID
    name: str
    description: str
    is_active: bool
    permissions: frozenset[str]


@final
@dataclass(frozen=True)
class MemberView:
    """A tenant member with the roles assigned to the membership."""

    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    membership_role: MembershipRole
    is_active: bool
    role_ids: frozenset[uuid.UUID] = field(compare=False)


def validate_permissions(permissions: Iterable[str]) -> frozenset[str]:
    """Validate permission codes against the system catalog."""
    codes = frozenset(permissions)
    unknown = codes - SYSTEM_PERMISSIONS.keys()
    if unknown:
        raise UnknownPermissionError(unknown)
    return codes


async def resolve_permissions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_role: MembershipRole,
    membership_id: uuid.UUID,
) -> frozenset[str]:
    """Resolve the caller's effective permissions as the union of assigned roles.

    The tenant owner implicitly holds every system permission; other members
    get the union of permissions from their active assigned roles. Evaluated
    on every request so permission changes take effect immediately.
    """
    if membership_role == OWNER_ROLE:
        return frozenset(SYSTEM_PERMISSIONS)
    result = await session.execute(
        select(RolePermission.permission)
        .join(Role, Role.id == RolePermission.role_id)
        .join(
            MembershipRoleAssignment,
            (MembershipRoleAssignment.role_id == Role.id)
            & (MembershipRoleAssignment.membership_id == membership_id),
        )
        .where(Role.tenant_id == tenant_id, Role.is_active)
    )
    return frozenset(result.scalars().all())


async def create_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    description: str,
    permissions: Iterable[str],
) -> RoleView:
    """Create a tenant role with a set of system-defined permissions."""
    codes = validate_permissions(permissions)
    role = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_active=True,
    )
    session.add(role)
    try:
        await session.flush()
        session.add_all(
            RolePermission(role_id=role.id, permission=code, tenant_id=tenant_id) for code in codes
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateRoleNameError from error
    except SQLAlchemyError:
        await session.rollback()
        raise
    return _role_view(role, codes)


async def _commit_or_raise(session: AsyncSession) -> None:
    """Commit, mapping unique-name violations to a domain error."""
    try:
        await session.flush()
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateRoleNameError from error
    except SQLAlchemyError:
        await session.rollback()
        raise


async def list_roles(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[RoleView]:
    """List all roles of the tenant with their permissions."""
    roles = (await session.execute(select(Role).where(Role.tenant_id == tenant_id))).scalars().all()
    result = await session.execute(
        select(RolePermission.role_id, RolePermission.permission).where(
            RolePermission.tenant_id == tenant_id
        )
    )
    permissions_by_role: dict[uuid.UUID, set[str]] = {}
    for role_id, permission in result.all():
        permissions_by_role.setdefault(role_id, set()).add(permission)
    return [
        _role_view(role, frozenset(permissions_by_role.get(role.id, ())))
        for role in sorted(roles, key=lambda role: role.created_at)
    ]


async def update_role(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
    permissions: Iterable[str] | None = None,
    is_active: bool | None = None,
) -> RoleView:
    """Edit a tenant role; None fields keep their current value."""
    role = await _load_role(session, tenant_id=tenant_id, role_id=role_id)
    codes: frozenset[str]
    if permissions is not None:
        codes = validate_permissions(permissions)
        _ = await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        await session.flush()
        session.add_all(
            RolePermission(role_id=role.id, permission=code, tenant_id=tenant_id) for code in codes
        )
    else:
        # Read the current permissions before committing: the commit ends the
        # transaction-local tenant context, so a post-commit read would be
        # denied by row level security.
        codes = frozenset(
            (
                await session.execute(
                    select(RolePermission.permission).where(RolePermission.role_id == role.id)
                )
            ).scalars()
        )
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if is_active is not None:
        role.is_active = is_active
    await _commit_or_raise(session)
    return _role_view(role, codes)


async def assign_roles(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    role_ids: Iterable[uuid.UUID],
) -> None:
    """Replace the roles assigned to a tenant membership."""
    membership = (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.id == membership_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise MembershipNotFoundError
    wanted = frozenset(role_ids)
    for role_id in wanted:
        _ = await _load_role(session, tenant_id=tenant_id, role_id=role_id)
    _ = await session.execute(
        delete(MembershipRoleAssignment).where(
            MembershipRoleAssignment.membership_id == membership_id
        )
    )
    await session.flush()
    session.add_all(
        MembershipRoleAssignment(membership_id=membership_id, role_id=role_id, tenant_id=tenant_id)
        for role_id in wanted
    )
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise


async def list_members(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[MemberView]:
    """List tenant members with their assigned roles."""
    result = await session.execute(
        select(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id)
    )
    rows = result.all()
    assignments = await session.execute(
        select(MembershipRoleAssignment.membership_id, MembershipRoleAssignment.role_id).where(
            MembershipRoleAssignment.tenant_id == tenant_id
        )
    )
    roles_by_membership: dict[uuid.UUID, set[uuid.UUID]] = {}
    for membership_id, role_id in assignments.all():
        roles_by_membership.setdefault(membership_id, set()).add(role_id)
    return [
        MemberView(
            membership_id=membership.id,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            membership_role=membership.role,
            is_active=membership.is_active,
            role_ids=frozenset(roles_by_membership.get(membership.id, ())),
        )
        for membership, user in rows
    ]


async def _load_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
) -> Role:
    role = (
        await session.execute(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if role is None:
        raise RoleNotFoundError
    return role


def _role_view(role: Role, permissions: frozenset[str]) -> RoleView:
    return RoleView(
        id=role.id,
        name=role.name,
        description=role.description,
        is_active=role.is_active,
        permissions=permissions,
    )
