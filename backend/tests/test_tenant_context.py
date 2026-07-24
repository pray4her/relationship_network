import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast, final

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException

from relationship_network_api import deps, rbac_service, tenant_context
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.models import Tenant, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@final
class ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


@final
class FakeSession:
    """Serves queued scalar results for the tenant/user lookups."""

    def __init__(self, scalars: list[object]) -> None:
        self._scalars = list(scalars)

    async def execute(self, _statement: object) -> ScalarResult:
        return ScalarResult(self._scalars.pop(0))


def as_session(fake: FakeSession) -> "AsyncSession":
    return cast("AsyncSession", cast("object", fake))


def make_tenant(*, mfa_required: bool = False) -> Tenant:
    return Tenant(id=TENANT_ID, name="Acme 科技", slug="acme-1234abcd", mfa_required=mfa_required)


def make_user(*, mfa_enabled: bool = False) -> User:
    return User(
        id=USER_ID,
        email="member@example.com",
        display_name="Tenant Member",
        password_hash="hash",
        is_active=True,
        totp_secret="SECRET" if mfa_enabled else None,
        totp_enabled_at=datetime.now(UTC) if mfa_enabled else None,
    )


def make_authentication(*, with_membership: bool = True) -> Authentication:
    membership = (
        MembershipView(
            membership_id=MEMBERSHIP_ID,
            tenant_id=TENANT_ID,
            tenant_name="Acme 科技",
            tenant_slug="acme-1234abcd",
            role="member",
        )
        if with_membership
        else None
    )
    return Authentication(
        user=UserView(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="member@example.com",
            display_name="Tenant Member",
        ),
        membership=membership,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        renewed=False,
    )


async def test_tenant_context_forbidden_without_membership() -> None:
    # Given an authenticated user with no active membership
    session = cast("AsyncSession", cast("object", None))

    # When the tenant context is resolved
    with pytest.raises(HTTPException) as captured:
        _ = await deps.get_tenant_context(session, make_authentication(with_membership=False))

    # Then access is forbidden
    assert captured.value.status_code == 403
    assert captured.value.detail == "no_active_membership"


async def test_tenant_context_pins_session_and_resolves_permissions(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given the tenant context dependencies
    pinned: list[uuid.UUID] = []

    async def fake_set_tenant_context(_session: object, tenant_id: uuid.UUID) -> None:
        pinned.append(tenant_id)

    async def fake_resolve_permissions(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        membership_role: str,
        membership_id: uuid.UUID,
    ) -> frozenset[str]:
        assert tenant_id == TENANT_ID
        assert membership_role == "member"
        assert membership_id == MEMBERSHIP_ID
        return frozenset({"roles:read"})

    monkeypatch.setattr(tenant_context, "set_tenant_context", fake_set_tenant_context)
    monkeypatch.setattr(rbac_service, "resolve_permissions", fake_resolve_permissions)
    session = as_session(FakeSession([make_tenant()]))

    # When the tenant context is resolved
    context = await deps.get_tenant_context(session, make_authentication())

    # Then the session is pinned to the tenant and permissions are resolved
    assert pinned == [TENANT_ID]
    assert context.membership.tenant_id == TENANT_ID
    assert context.permissions == frozenset({"roles:read"})


async def test_require_permission_allows_and_denies(monkeypatch: MonkeyPatch) -> None:
    # Given a resolved tenant context with one permission
    async def fake_set_tenant_context(_session: object, _tenant_id: uuid.UUID) -> None:
        return None

    async def fake_resolve_permissions(_session: object, **_kwargs: object) -> frozenset[str]:
        return frozenset({"roles:read"})

    monkeypatch.setattr(tenant_context, "set_tenant_context", fake_set_tenant_context)
    monkeypatch.setattr(rbac_service, "resolve_permissions", fake_resolve_permissions)
    session = as_session(FakeSession([make_tenant(), make_tenant()]))

    # When a held permission is required
    allowed = await deps.require_permission("roles:read")(
        await deps.get_tenant_context(session, make_authentication())
    )

    # Then the context is returned
    assert "roles:read" in allowed.permissions

    # When a missing permission is required
    with pytest.raises(HTTPException) as captured:
        _ = await deps.require_permission("roles:manage")(
            await deps.get_tenant_context(session, make_authentication())
        )

    # Then access is denied
    assert captured.value.status_code == 403
    assert captured.value.detail == "permission_denied"


async def test_tenant_context_rejects_member_without_mfa_when_tenant_enforces_it(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given a tenant enforcing MFA and a member without TOTP enabled
    async def fake_set_tenant_context(_session: object, _tenant_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(tenant_context, "set_tenant_context", fake_set_tenant_context)
    session = as_session(FakeSession([make_tenant(mfa_required=True), make_user()]))

    # When the tenant context is resolved
    with pytest.raises(HTTPException) as captured:
        _ = await deps.get_tenant_context(session, make_authentication())

    # Then access is forbidden with the pinned detail
    assert captured.value.status_code == 403
    assert captured.value.detail == "mfa_required"


async def test_tenant_context_allows_member_with_mfa_when_tenant_enforces_it(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given a tenant enforcing MFA and a member with TOTP enabled
    async def fake_set_tenant_context(_session: object, _tenant_id: uuid.UUID) -> None:
        return None

    async def fake_resolve_permissions(_session: object, **_kwargs: object) -> frozenset[str]:
        return frozenset()

    monkeypatch.setattr(tenant_context, "set_tenant_context", fake_set_tenant_context)
    monkeypatch.setattr(rbac_service, "resolve_permissions", fake_resolve_permissions)
    session = as_session(FakeSession([make_tenant(mfa_required=True), make_user(mfa_enabled=True)]))

    # When the tenant context is resolved
    context = await deps.get_tenant_context(session, make_authentication())

    # Then access is granted
    assert context.membership.tenant_id == TENANT_ID
