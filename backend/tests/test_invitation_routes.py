import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import invitation_service, tasks, tenant_context
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_settings,
    get_tenant_context,
)
from relationship_network_api.invitation_service import (
    AcceptedInvitation,
    AlreadyInTenantError,
    CreatedInvitation,
    EmailAlreadyMemberError,
    InvitationAlreadyAcceptedError,
    InvitationAlreadyPendingError,
    InvitationEmailMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    InvitationPreview,
    InvitationView,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import User

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBERSHIP_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
INVITATION_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
EXPIRES_AT = datetime(2030, 1, 1, tzinfo=UTC)
CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def make_context(*, permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=MEMBERSHIP_ID,
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="owner",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(id=USER_ID, email="owner@example.com", display_name="Tenant Owner"),
            membership=membership,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            renewed=False,
        ),
        membership=membership,
        permissions=permissions,
    )


def make_invitation_view(*, status: str = "pending") -> InvitationView:
    return InvitationView(
        id=INVITATION_ID,
        email="invitee@example.com",
        status=cast("invitation_service.InvitationStatus", status),
        expires_at=EXPIRES_AT,
        accepted_at=None,
        revoked_at=None,
        created_at=CREATED_AT,
    )


def make_client(context: TenantContext | None) -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    def override_settings() -> object:
        return SimpleNamespace(
            invitation_ttl_seconds=604800,
            app_base_url="http://localhost:3000",
        )

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    if context is not None:

        def override_context() -> TenantContext:
            return context

        app.dependency_overrides[get_tenant_context] = override_context
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_rls_context(monkeypatch: MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(tenant_context, "set_tenant_context", _noop)


@pytest.fixture
def stub_email_task(monkeypatch: MonkeyPatch) -> list[tuple[str, str, str]]:
    enqueued: list[tuple[str, str, str]] = []

    @staticmethod
    def delay(email: str, tenant_name: str, invite_url: str) -> None:
        enqueued.append((email, tenant_name, invite_url))

    monkeypatch.setattr(
        tasks,
        "send_invitation_email",
        SimpleNamespace(delay=delay),
    )
    return enqueued


def test_create_invitation_returns_token_and_enqueues_email(
    monkeypatch: MonkeyPatch,
    stub_email_task: list[tuple[str, str, str]],
) -> None:
    # Given a caller holding members:invite
    async def fake_create_invitation(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        email: str,
        invited_by: uuid.UUID,
        invitation_ttl_seconds: int,
    ) -> CreatedInvitation:
        assert tenant_id == TENANT_ID
        assert email == "invitee@example.com"
        assert invited_by == USER_ID
        assert invitation_ttl_seconds == 604800
        return CreatedInvitation(invitation=make_invitation_view(), token="raw-token")

    monkeypatch.setattr(invitation_service, "create_invitation", fake_create_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is created
    response = client.post("/invitations", json={"email": "invitee@example.com"})

    # Then the raw token and invite URL are returned once and the email is enqueued
    assert response.status_code == 201
    body = response.json()
    assert body["token"] == "raw-token"
    assert body["invite_url"] == "http://localhost:3000/invite/raw-token"
    assert body["invitation"]["status"] == "pending"
    assert stub_email_task == [
        ("invitee@example.com", "Acme 科技", "http://localhost:3000/invite/raw-token")
    ]


def test_create_invitation_survives_email_broker_outage(monkeypatch: MonkeyPatch) -> None:
    # Given the email broker being unavailable
    async def fake_create_invitation(_session: object, **_kwargs: object) -> CreatedInvitation:
        return CreatedInvitation(invitation=make_invitation_view(), token="raw-token")

    @staticmethod
    def delay(*_args: object) -> None:
        raise ConnectionError

    monkeypatch.setattr(invitation_service, "create_invitation", fake_create_invitation)
    monkeypatch.setattr(tasks, "send_invitation_email", SimpleNamespace(delay=delay))
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is created
    response = client.post("/invitations", json={"email": "invitee@example.com"})

    # Then the request still succeeds
    assert response.status_code == 201


def test_create_invitation_denied_without_members_invite() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When an invitation is created
    response = client.post("/invitations", json={"email": "invitee@example.com"})

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_create_invitation_conflict_on_active_member(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting the email is already a member
    async def fake_create_invitation(_session: object, **_kwargs: object) -> CreatedInvitation:
        raise EmailAlreadyMemberError

    monkeypatch.setattr(invitation_service, "create_invitation", fake_create_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is created
    response = client.post("/invitations", json={"email": "member@example.com"})

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "email_already_member"}


def test_create_invitation_conflict_on_pending_duplicate(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting a pending invitation for the email
    async def fake_create_invitation(_session: object, **_kwargs: object) -> CreatedInvitation:
        raise InvitationAlreadyPendingError

    monkeypatch.setattr(invitation_service, "create_invitation", fake_create_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is created
    response = client.post("/invitations", json={"email": "invitee@example.com"})

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "invitation_already_pending"}


def test_list_invitations_allowed_with_members_read(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:read
    async def fake_list_invitations(
        _session: object,
        *,
        tenant_id: uuid.UUID,
    ) -> list[InvitationView]:
        assert tenant_id == TENANT_ID
        return [make_invitation_view(), make_invitation_view(status="revoked")]

    monkeypatch.setattr(invitation_service, "list_invitations", fake_list_invitations)
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When the invitations are listed
    response = client.get("/invitations")

    # Then the invitation views are returned
    assert response.status_code == 200
    body = response.json()
    assert [entry["status"] for entry in body] == ["pending", "revoked"]
    assert body[0]["id"] == str(INVITATION_ID)


def test_list_invitations_denied_without_members_read() -> None:
    # Given a caller without members:read
    client = make_client(make_context(permissions=frozenset()))

    # When the invitations are listed
    response = client.get("/invitations")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_revoke_invitation_returns_updated_view(monkeypatch: MonkeyPatch) -> None:
    # Given a caller holding members:invite
    async def fake_revoke_invitation(
        _session: object,
        *,
        tenant_id: uuid.UUID,
        invitation_id: uuid.UUID,
    ) -> InvitationView:
        assert tenant_id == TENANT_ID
        assert invitation_id == INVITATION_ID
        return make_invitation_view(status="revoked")

    monkeypatch.setattr(invitation_service, "revoke_invitation", fake_revoke_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is revoked
    response = client.post(f"/invitations/{INVITATION_ID}/revoke")

    # Then the revoked view is returned
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_revoke_invitation_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service not finding the invitation in the caller's tenant
    async def fake_revoke_invitation(_session: object, **_kwargs: object) -> InvitationView:
        raise InvitationNotFoundError

    monkeypatch.setattr(invitation_service, "revoke_invitation", fake_revoke_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When a missing or foreign invitation is revoked
    response = client.post(f"/invitations/{uuid.uuid4()}/revoke")

    # Then the miss is reported without leaking existence
    assert response.status_code == 404
    assert response.json() == {"detail": "invitation_not_found"}


def test_revoke_invitation_conflict_when_already_accepted(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting the invitation was already accepted
    async def fake_revoke_invitation(_session: object, **_kwargs: object) -> InvitationView:
        raise InvitationAlreadyAcceptedError

    monkeypatch.setattr(invitation_service, "revoke_invitation", fake_revoke_invitation)
    client = make_client(make_context(permissions=frozenset({"members:invite"})))

    # When the invitation is revoked
    response = client.post(f"/invitations/{INVITATION_ID}/revoke")

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "invitation_already_accepted"}


def test_revoke_invitation_denied_without_members_invite() -> None:
    # Given a caller holding only members:read
    client = make_client(make_context(permissions=frozenset({"members:read"})))

    # When an invitation is revoked
    response = client.post(f"/invitations/{INVITATION_ID}/revoke")

    # Then access is denied
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_preview_invitation_is_public(monkeypatch: MonkeyPatch) -> None:
    # Given an anonymous caller and a pending invitation
    async def fake_preview_invitation(_session: object, *, token: str) -> InvitationPreview:
        assert token == "raw-token"
        return InvitationPreview(
            email="invitee@example.com",
            tenant_name="Acme 科技",
            expires_at=EXPIRES_AT,
        )

    monkeypatch.setattr(invitation_service, "preview_invitation", fake_preview_invitation)
    client = make_client(None)

    # When the invitation is previewed
    response = client.get("/invitations/preview", params={"token": "raw-token"})

    # Then the public view is returned without authentication
    assert response.status_code == 200
    assert response.json() == {
        "email": "invitee@example.com",
        "tenant_name": "Acme 科技",
        "expires_at": "2030-01-01T00:00:00Z",
    }


def test_preview_invitation_invalid_is_uniform_not_found(monkeypatch: MonkeyPatch) -> None:
    # Given the service rejecting the token
    async def fake_preview_invitation(_session: object, **_kwargs: object) -> InvitationPreview:
        raise InvitationInvalidError

    monkeypatch.setattr(invitation_service, "preview_invitation", fake_preview_invitation)
    client = make_client(None)

    # When an unknown, expired, revoked, or used token is previewed
    response = client.get("/invitations/preview", params={"token": "bad-token"})

    # Then the failure is uniform and does not enumerate invitations
    assert response.status_code == 404
    assert response.json() == {"detail": "invitation_invalid"}


def make_accept_client(authentication: Authentication | None) -> TestClient:
    app = create_app(checks=())

    def override_authentication() -> Authentication | None:
        return authentication

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_authentication] = override_authentication
    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def make_authentication() -> Authentication:
    return Authentication(
        user=UserView(id=USER_ID, email="invitee@example.com", display_name="受邀用户"),
        membership=None,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        renewed=False,
    )


def stub_accept(monkeypatch: MonkeyPatch) -> None:
    async def fake_load_user(_session: object, *, user_id: uuid.UUID) -> User:
        assert user_id == USER_ID
        return User(
            id=USER_ID,
            email="invitee@example.com",
            display_name="受邀用户",
            password_hash="hash",
            is_active=True,
        )

    async def fake_accept_invitation(
        _session: object,
        *,
        token: str,
        user: User,
    ) -> AcceptedInvitation:
        assert token == "raw-token"
        assert user.email == "invitee@example.com"
        return AcceptedInvitation(
            tenant_id=TENANT_ID,
            tenant_name="Acme 科技",
            tenant_slug="acme-1234abcd",
            role="member",
        )

    monkeypatch.setattr(invitation_service, "load_user", fake_load_user)
    monkeypatch.setattr(invitation_service, "accept_invitation", fake_accept_invitation)


def test_accept_invitation_returns_membership(monkeypatch: MonkeyPatch) -> None:
    # Given an authenticated invitee
    stub_accept(monkeypatch)
    client = make_accept_client(make_authentication())

    # When the invitation is accepted
    response = client.post("/invitations/accept", json={"token": "raw-token"})

    # Then the granted membership is returned
    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": str(TENANT_ID),
        "tenant_name": "Acme 科技",
        "tenant_slug": "acme-1234abcd",
        "role": "member",
    }


def test_accept_invitation_requires_authentication() -> None:
    # Given an anonymous caller
    client = make_accept_client(None)

    # When an invitation is accepted
    response = client.post("/invitations/accept", json={"token": "raw-token"})

    # Then the caller is rejected
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (InvitationInvalidError(), 404, "invitation_invalid"),
        (InvitationEmailMismatchError(), 403, "invitation_email_mismatch"),
        (AlreadyInTenantError(), 409, "already_in_tenant"),
    ],
)
def test_accept_invitation_maps_service_errors(
    monkeypatch: MonkeyPatch,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    # Given the service rejecting the acceptance
    async def fake_load_user(_session: object, **_kwargs: object) -> User:
        return User(
            id=USER_ID,
            email="invitee@example.com",
            display_name="受邀用户",
            password_hash="hash",
            is_active=True,
        )

    async def fake_accept_invitation(_session: object, **_kwargs: object) -> AcceptedInvitation:
        raise error

    monkeypatch.setattr(invitation_service, "load_user", fake_load_user)
    monkeypatch.setattr(invitation_service, "accept_invitation", fake_accept_invitation)
    client = make_accept_client(make_authentication())

    # When the invitation is accepted
    response = client.post("/invitations/accept", json={"token": "raw-token"})

    # Then the pinned error contract is returned
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
