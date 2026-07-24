import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast, final

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context
from relationship_network_api.invitation_service import (
    AlreadyInTenantError,
    EmailAlreadyMemberError,
    InvitationAlreadyAcceptedError,
    InvitationAlreadyPendingError,
    InvitationEmailMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    accept_invitation,
    create_invitation,
    invitation_status,
    list_invitations,
    preview_invitation,
    revoke_invitation,
)
from relationship_network_api.models import Tenant, TenantInvitation, TenantMembership, User
from relationship_network_api.security import hash_session_token

pytestmark = pytest.mark.anyio

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
INVITATION_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


@final
class FakeResult:
    def __init__(self, *, scalar: object = None, rows: Iterable[object] = ()) -> None:
        self._scalar = scalar
        self._rows = list(rows)

    def scalar_one_or_none(self) -> object:
        return self._scalar

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[object]:
        return self._rows


@final
class SpySession:
    def __init__(self, results: list[FakeResult]) -> None:
        self._results = list(results)
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def execute(self, _statement: object) -> FakeResult:
        return self._results.pop(0)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def as_session(spy: SpySession) -> AsyncSession:
    return cast("AsyncSession", cast("object", spy))


@pytest.fixture(autouse=True)
def _stub_rls_context(monkeypatch: MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(tenant_context, "set_tenant_context", _noop)
    monkeypatch.setattr(tenant_context, "set_user_context", _noop)
    monkeypatch.setattr(tenant_context, "set_invitation_token_context", _noop)


def make_invitation(
    *,
    email: str = "invitee@example.com",
    accepted_at: datetime | None = None,
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> TenantInvitation:
    return TenantInvitation(
        id=INVITATION_ID,
        tenant_id=TENANT_ID,
        email=email,
        token_hash=hash_session_token("raw-token"),
        invited_by=uuid.uuid4(),
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
        accepted_at=accepted_at,
        revoked_at=revoked_at,
        created_at=datetime.now(UTC),
    )


def make_user(*, email: str = "invitee@example.com") -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        display_name="受邀用户",
        password_hash="hash",
        is_active=True,
    )


def make_tenant() -> Tenant:
    return Tenant(id=TENANT_ID, name="Acme 科技", slug="acme-1234abcd")


def test_invitation_status_priority() -> None:
    now = datetime.now(UTC)
    # Given invitations in every lifecycle state
    # Then revoked wins over accepted, accepted wins over expiry
    assert invitation_status(make_invitation(revoked_at=now), now=now) == "revoked"
    assert (
        invitation_status(
            make_invitation(accepted_at=now, revoked_at=now),
            now=now,
        )
        == "revoked"
    )
    assert invitation_status(make_invitation(accepted_at=now), now=now) == "accepted"
    assert (
        invitation_status(make_invitation(expires_at=now - timedelta(seconds=1)), now=now)
        == "expired"
    )
    assert invitation_status(make_invitation(), now=now) == "pending"


async def test_create_invitation_returns_raw_token_once() -> None:
    # Given no membership and no pending invitation for the email
    spy = SpySession([FakeResult(), FakeResult()])

    # When the invitation is created
    created = await create_invitation(
        as_session(spy),
        tenant_id=TENANT_ID,
        email="  Invitee@Example.com ",
        invited_by=uuid.uuid4(),
        invitation_ttl_seconds=604800,
    )

    # Then the invitation stores only the token hash with a normalized email
    assert created.invitation.email == "invitee@example.com"
    assert created.invitation.status == "pending"
    assert created.token not in created.invitation.__repr__()
    invitation = cast("TenantInvitation", spy.added[0])
    assert invitation.token_hash == hash_session_token(created.token)
    assert created.token not in invitation.token_hash
    assert spy.commit_calls == 1


async def test_create_invitation_rejects_active_member() -> None:
    # Given an active membership for the invited email in the tenant
    spy = SpySession([FakeResult(scalar=TenantMembership(id=uuid.uuid4()))])

    # When the invitation is created
    with pytest.raises(EmailAlreadyMemberError):
        _ = await create_invitation(
            as_session(spy),
            tenant_id=TENANT_ID,
            email="invitee@example.com",
            invited_by=uuid.uuid4(),
            invitation_ttl_seconds=604800,
        )

    # Then nothing is persisted
    assert spy.added == []
    assert spy.commit_calls == 0


async def test_create_invitation_rejects_pending_duplicate() -> None:
    # Given a pending invitation for the same email and tenant
    spy = SpySession([FakeResult(), FakeResult(scalar=make_invitation())])

    # When another invitation is created
    with pytest.raises(InvitationAlreadyPendingError):
        _ = await create_invitation(
            as_session(spy),
            tenant_id=TENANT_ID,
            email="invitee@example.com",
            invited_by=uuid.uuid4(),
            invitation_ttl_seconds=604800,
        )

    # Then nothing is persisted
    assert spy.added == []


async def test_list_invitations_returns_views_newest_first() -> None:
    # Given two stored invitations
    newest = make_invitation(email="new@example.com")
    oldest = make_invitation(email="old@example.com")
    spy = SpySession([FakeResult(rows=[newest, oldest])])

    # When the invitations are listed
    views = await list_invitations(as_session(spy), tenant_id=TENANT_ID)

    # Then views carry the computed status in the stored order
    assert [view.email for view in views] == ["new@example.com", "old@example.com"]
    assert all(view.status == "pending" for view in views)


async def test_revoke_invitation_marks_pending_as_revoked() -> None:
    # Given a pending invitation
    invitation = make_invitation()
    spy = SpySession([FakeResult(scalar=invitation)])

    # When it is revoked
    view = await revoke_invitation(
        as_session(spy),
        tenant_id=TENANT_ID,
        invitation_id=INVITATION_ID,
    )

    # Then the revocation is committed
    assert view.status == "revoked"
    assert invitation.revoked_at is not None
    assert spy.commit_calls == 1


async def test_revoke_invitation_is_idempotent_when_already_revoked() -> None:
    # Given an already revoked invitation
    invitation = make_invitation(revoked_at=datetime.now(UTC))
    spy = SpySession([FakeResult(scalar=invitation)])

    # When it is revoked again
    view = await revoke_invitation(
        as_session(spy),
        tenant_id=TENANT_ID,
        invitation_id=INVITATION_ID,
    )

    # Then the view is returned without another commit
    assert view.status == "revoked"
    assert spy.commit_calls == 0


async def test_revoke_invitation_rejects_missing() -> None:
    # Given no invitation for the id in the tenant
    spy = SpySession([FakeResult()])

    # When it is revoked
    with pytest.raises(InvitationNotFoundError):
        _ = await revoke_invitation(
            as_session(spy),
            tenant_id=TENANT_ID,
            invitation_id=uuid.uuid4(),
        )


async def test_revoke_invitation_rejects_accepted() -> None:
    # Given an accepted invitation
    spy = SpySession([FakeResult(scalar=make_invitation(accepted_at=datetime.now(UTC)))])

    # When it is revoked
    with pytest.raises(InvitationAlreadyAcceptedError):
        _ = await revoke_invitation(
            as_session(spy),
            tenant_id=TENANT_ID,
            invitation_id=INVITATION_ID,
        )


async def test_preview_invitation_returns_public_view() -> None:
    # Given a pending invitation
    spy = SpySession([FakeResult(scalar=make_invitation()), FakeResult(scalar=make_tenant())])

    # When it is previewed by token
    preview = await preview_invitation(as_session(spy), token="raw-token")

    # Then the public view carries email, tenant name, and expiry
    assert preview.email == "invitee@example.com"
    assert preview.tenant_name == "Acme 科技"


@pytest.mark.parametrize(
    "invitation",
    [
        None,
        make_invitation(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        make_invitation(revoked_at=datetime.now(UTC)),
        make_invitation(accepted_at=datetime.now(UTC)),
    ],
    ids=["unknown", "expired", "revoked", "accepted"],
)
async def test_preview_invitation_rejects_non_pending_uniformly(
    invitation: TenantInvitation | None,
) -> None:
    # Given an invitation that is unknown, expired, revoked, or used
    spy = SpySession([FakeResult(scalar=invitation)])

    # When it is previewed
    with pytest.raises(InvitationInvalidError):
        _ = await preview_invitation(as_session(spy), token="raw-token")


async def test_accept_invitation_joins_issuing_tenant_as_member() -> None:
    # Given a pending invitation and a user with no membership
    invitation = make_invitation()
    spy = SpySession(
        [
            FakeResult(scalar=invitation),
            FakeResult(),
            FakeResult(scalar=make_tenant()),
        ]
    )

    # When the invitation is accepted
    accepted = await accept_invitation(as_session(spy), token="raw-token", user=make_user())

    # Then a member membership is created in the issuing tenant
    assert accepted.tenant_id == TENANT_ID
    assert accepted.role == "member"
    membership = cast("TenantMembership", spy.added[0])
    assert membership.tenant_id == TENANT_ID
    assert membership.role == "member"
    assert invitation.accepted_at is not None
    assert spy.commit_calls == 1


async def test_accept_invitation_rejects_email_mismatch() -> None:
    # Given a pending invitation for another email
    spy = SpySession([FakeResult(scalar=make_invitation())])

    # When a different user accepts
    with pytest.raises(InvitationEmailMismatchError):
        _ = await accept_invitation(
            as_session(spy),
            token="raw-token",
            user=make_user(email="other@example.com"),
        )

    # Then nothing is persisted
    assert spy.added == []


async def test_accept_invitation_rejects_user_already_in_tenant() -> None:
    # Given a pending invitation and a user holding an active membership
    spy = SpySession(
        [
            FakeResult(scalar=make_invitation()),
            FakeResult(scalar=TenantMembership(id=uuid.uuid4())),
        ]
    )

    # When the user accepts
    with pytest.raises(AlreadyInTenantError):
        _ = await accept_invitation(as_session(spy), token="raw-token", user=make_user())

    # Then the invitation stays pending
    assert spy.added == []


async def test_accept_invitation_rejects_invalid_token() -> None:
    # Given an unknown token
    spy = SpySession([FakeResult()])

    # When it is accepted
    with pytest.raises(InvitationInvalidError):
        _ = await accept_invitation(as_session(spy), token="raw-token", user=make_user())
