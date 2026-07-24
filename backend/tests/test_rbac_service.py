import uuid
from collections.abc import Iterable
from typing import cast, final

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import rbac_service
from relationship_network_api.rbac_service import (
    SYSTEM_PERMISSIONS,
    DuplicateRoleNameError,
    MembershipNotFoundError,
    RoleNotFoundError,
    UnknownPermissionError,
    validate_permissions,
)

pytestmark = pytest.mark.anyio


@final
class ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


@final
class SpySession:
    def __init__(self, *, scalar: object = None, fail_on_commit: Exception | None = None) -> None:
        self._scalar = scalar
        self._fail_on_commit = fail_on_commit
        self.added: list[object] = []
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def add_all(self, instances: Iterable[object]) -> None:
        self.added.extend(instances)

    async def execute(self, _statement: object) -> ScalarResult:
        return ScalarResult(self._scalar)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        if self._fail_on_commit is not None:
            raise self._fail_on_commit

    async def rollback(self) -> None:
        self.rollback_calls += 1


def as_session(spy: SpySession) -> AsyncSession:
    return cast("AsyncSession", cast("object", spy))


def test_validate_permissions_accepts_catalog_codes() -> None:
    # Given system-defined permission codes
    codes = validate_permissions(["roles:read", "members:manage", "roles:read"])

    # Then they are accepted and deduplicated
    assert codes == frozenset({"roles:read", "members:manage"})


def test_validate_permissions_rejects_unknown_codes() -> None:
    # Given a permission code outside the catalog
    with pytest.raises(UnknownPermissionError) as captured:
        _ = validate_permissions(["roles:read", "roles:fly"])

    # Then the unknown codes are reported
    assert captured.value.codes == frozenset({"roles:fly"})


async def test_resolve_permissions_grants_owner_every_permission() -> None:
    # Given a tenant owner membership
    permissions = await rbac_service.resolve_permissions(
        cast("AsyncSession", cast("object", None)),
        tenant_id=uuid.uuid4(),
        membership_role="owner",
        membership_id=uuid.uuid4(),
    )

    # Then every system permission is granted implicitly
    assert permissions == frozenset(SYSTEM_PERMISSIONS)


async def test_create_role_maps_duplicate_name_to_conflict() -> None:
    # Given the database rejecting a duplicate tenant role name
    spy = SpySession(
        fail_on_commit=IntegrityError("INSERT INTO roles", {}, Exception("duplicate")),
    )

    # When the role is created
    with pytest.raises(DuplicateRoleNameError):
        _ = await rbac_service.create_role(
            as_session(spy),
            tenant_id=uuid.uuid4(),
            name="运营",
            description="",
            permissions=["roles:read"],
        )

    # Then the transaction is rolled back
    assert spy.rollback_calls == 1


async def test_update_role_rejects_missing_or_foreign_role() -> None:
    # Given a role lookup that finds nothing in the caller's tenant
    spy = SpySession(scalar=None)

    # When the role is updated
    with pytest.raises(RoleNotFoundError):
        _ = await rbac_service.update_role(
            as_session(spy),
            tenant_id=uuid.uuid4(),
            role_id=uuid.uuid4(),
            name="新名字",
        )


async def test_assign_roles_rejects_missing_or_foreign_membership() -> None:
    # Given a membership lookup that finds nothing in the caller's tenant
    spy = SpySession(scalar=None)

    # When roles are assigned
    with pytest.raises(MembershipNotFoundError):
        _ = await rbac_service.assign_roles(
            as_session(spy),
            tenant_id=uuid.uuid4(),
            membership_id=uuid.uuid4(),
            role_ids=[],
        )
