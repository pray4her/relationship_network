import uuid
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context
from relationship_network_api.invitation_service import AlreadyInTenantError
from relationship_network_api.models import MEMBER_ROLE, OWNER_ROLE, TenantMembership

NO_ACTIVE_MEMBERSHIP_DETAIL: Final = "no_active_membership"
PROTECTED_OWNER_DETAIL: Final = "protected_owner"
MEMBERSHIP_NOT_FOUND_DETAIL: Final = "membership_not_found"


@final
class ProtectedOwnerError(Exception):
    """Raised when a lifecycle operation targets the tenant owner."""


@final
class MembershipNotFoundError(Exception):
    """Raised when a membership does not exist in the caller's tenant."""


def _ensure_not_owner(membership: TenantMembership) -> None:
    if membership.role == OWNER_ROLE:
        raise ProtectedOwnerError


async def deactivate_member(session: AsyncSession, membership: TenantMembership) -> None:
    """Deactivate a membership; the tenant owner can never be deactivated."""
    _ensure_not_owner(membership)
    membership.is_active = False
    await session.flush()


async def activate_member(session: AsyncSession, membership: TenantMembership) -> None:
    """Reactivate a deactivated membership, keeping the single-active-tenant invariant."""
    # Pin the user context so row level security exposes the user's memberships
    # in other tenants, then refuse reactivation when one is already active.
    await tenant_context.set_user_context(session, membership.user_id)
    other = (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == membership.user_id,
                TenantMembership.tenant_id != membership.tenant_id,
                TenantMembership.is_active,
            )
        )
    ).scalar_one_or_none()
    if other is not None:
        raise AlreadyInTenantError
    membership.is_active = True
    await session.flush()


async def demote_member(session: AsyncSession, membership: TenantMembership) -> None:
    """Demote a member to the plain member role; the tenant owner can never be demoted."""
    _ensure_not_owner(membership)
    membership.role = MEMBER_ROLE
    await session.flush()


async def remove_member(session: AsyncSession, membership: TenantMembership) -> None:
    """Remove a membership; the tenant owner can never be removed."""
    _ensure_not_owner(membership)
    await session.delete(membership)
    await session.flush()


async def deactivate_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> None:
    """Deactivate a tenant membership by id, committing the change."""
    membership = await _load_membership(session, tenant_id=tenant_id, membership_id=membership_id)
    await deactivate_member(session, membership)
    await _commit(session)


async def activate_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> None:
    """Reactivate a tenant membership by id, committing the change."""
    membership = await _load_membership(session, tenant_id=tenant_id, membership_id=membership_id)
    await activate_member(session, membership)
    await _commit(session)


async def remove_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> None:
    """Remove a tenant membership by id, committing the change."""
    membership = await _load_membership(session, tenant_id=tenant_id, membership_id=membership_id)
    await remove_member(session, membership)
    await _commit(session)


async def _load_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> TenantMembership:
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
    return membership


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
