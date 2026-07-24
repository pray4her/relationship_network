from typing import Final, final

from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.models import MEMBER_ROLE, OWNER_ROLE, TenantMembership

NO_ACTIVE_MEMBERSHIP_DETAIL: Final = "no_active_membership"


@final
class ProtectedOwnerError(Exception):
    """Raised when a lifecycle operation targets the tenant owner."""


def _ensure_not_owner(membership: TenantMembership) -> None:
    if membership.role == OWNER_ROLE:
        raise ProtectedOwnerError


async def deactivate_member(session: AsyncSession, membership: TenantMembership) -> None:
    """Deactivate a membership; the tenant owner can never be deactivated."""
    _ensure_not_owner(membership)
    membership.is_active = False
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
