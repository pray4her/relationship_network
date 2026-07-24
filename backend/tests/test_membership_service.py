import uuid
from types import SimpleNamespace
from typing import cast, final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.invitation_service import AlreadyInTenantError
from relationship_network_api.membership_service import (
    ProtectedOwnerError,
    activate_member,
    deactivate_member,
    demote_member,
    remove_member,
)
from relationship_network_api.models import MembershipRole, TenantMembership

pytestmark = pytest.mark.anyio


@final
class SpySession:
    def __init__(self, *, has_other_active_membership: bool = False) -> None:
        self.deleted: list[object] = []
        self.flush_calls = 0
        self._has_other_active_membership = has_other_active_membership

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)

    async def execute(self, _statement: object, _params: object = None) -> object:
        other = object() if self._has_other_active_membership else None
        return SimpleNamespace(scalar_one_or_none=lambda: other)

    async def flush(self) -> None:
        self.flush_calls += 1


def as_session(spy: SpySession) -> AsyncSession:
    return cast("AsyncSession", cast("object", spy))


def make_membership(role: MembershipRole) -> TenantMembership:
    return TenantMembership(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        is_active=True,
    )


async def test_deactivate_owner_is_refused() -> None:
    # Given a membership for the tenant owner
    owner = make_membership("owner")
    spy = SpySession()

    # When deactivation is attempted
    with pytest.raises(ProtectedOwnerError):
        await deactivate_member(as_session(spy), owner)

    # Then nothing is persisted
    assert owner.is_active
    assert spy.flush_calls == 0


async def test_demote_owner_is_refused() -> None:
    # Given a membership for the tenant owner
    owner = make_membership("owner")
    spy = SpySession()

    # When demotion is attempted
    with pytest.raises(ProtectedOwnerError):
        await demote_member(as_session(spy), owner)

    # Then the role is unchanged
    assert owner.role == "owner"
    assert spy.flush_calls == 0


async def test_remove_owner_is_refused() -> None:
    # Given a membership for the tenant owner
    owner = make_membership("owner")
    spy = SpySession()

    # When removal is attempted
    with pytest.raises(ProtectedOwnerError):
        await remove_member(as_session(spy), owner)

    # Then the row is never deleted
    assert spy.deleted == []


async def test_deactivate_plain_member_is_allowed() -> None:
    # Given a membership for a plain member
    member = make_membership("member")
    spy = SpySession()

    # When deactivation runs
    await deactivate_member(as_session(spy), member)

    # Then the membership is deactivated and flushed
    assert not member.is_active
    assert spy.flush_calls == 1


async def test_demote_plain_member_is_allowed() -> None:
    # Given a membership for a plain member
    member = make_membership("member")
    spy = SpySession()

    # When demotion runs
    await demote_member(as_session(spy), member)

    # Then the operation is a no-op success for the already-plain member
    assert member.role == "member"
    assert spy.flush_calls == 1


async def test_remove_plain_member_is_allowed() -> None:
    # Given a membership for a plain member
    member = make_membership("member")
    spy = SpySession()

    # When removal runs
    await remove_member(as_session(spy), member)

    # Then the row is deleted and flushed
    assert spy.deleted == [member]
    assert spy.flush_calls == 1


async def test_activate_member_flips_active_flag() -> None:
    # Given a deactivated membership
    member = make_membership("member")
    member.is_active = False
    spy = SpySession()

    # When activation runs
    await activate_member(as_session(spy), member)

    # Then the membership is active again and flushed
    assert member.is_active
    assert spy.flush_calls == 1


async def test_activate_member_rejects_user_active_in_other_tenant() -> None:
    # Given a deactivated membership whose user is active in another tenant
    member = make_membership("member")
    member.is_active = False
    spy = SpySession(has_other_active_membership=True)

    # When activation is attempted
    with pytest.raises(AlreadyInTenantError):
        await activate_member(as_session(spy), member)

    # Then the membership stays deactivated
    assert not member.is_active
    assert spy.flush_calls == 0
