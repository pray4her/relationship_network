import uuid
from collections import deque
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Final, cast, final

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import auth_service, invitation_service, tenant_context, usage_service
from relationship_network_api.auth_service import (
    AuthResult,
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    MfaPending,
)
from relationship_network_api.invitation_service import (
    InvitationEmailMismatchError,
    InvitationInvalidError,
)
from relationship_network_api.models import (
    AuthSession,
    MembershipRole,
    MfaChallenge,
    Tenant,
    TenantInvitation,
    TenantMembership,
    User,
)
from relationship_network_api.security import DUMMY_PASSWORD_HASH, hash_password

SESSION_TTL_SECONDS: Final = 1209600
RENEWAL_WINDOW_SECONDS: Final = 86400

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _stub_rls_context(monkeypatch: MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(tenant_context, "set_tenant_context", _noop)
    monkeypatch.setattr(tenant_context, "set_user_context", _noop)


@pytest.fixture(autouse=True)
def _stub_trial_subscription(monkeypatch: MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(usage_service, "start_trial_subscription", _noop)


@final
class ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


@final
class SpySession:
    def __init__(
        self,
        *,
        execute_results: Sequence[object] = (),
        fail_on_flush: Exception | None = None,
        fail_on_commit: Exception | None = None,
    ) -> None:
        self._execute_results: deque[ScalarResult] = deque(
            ScalarResult(value) for value in execute_results
        )
        self._fail_on_flush = fail_on_flush
        self._fail_on_commit = fail_on_commit
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)

    async def flush(self) -> None:
        self.flush_calls += 1
        if self._fail_on_flush is not None:
            raise self._fail_on_flush

    async def commit(self) -> None:
        self.commit_calls += 1
        if self._fail_on_commit is not None:
            raise self._fail_on_commit

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def execute(self, _statement: object) -> ScalarResult:
        return self._execute_results.popleft()


def as_session(spy: SpySession) -> AsyncSession:
    return cast("AsyncSession", cast("object", spy))


def make_service() -> AuthService:
    return AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
    )


def make_user(*, email: str = "owner@example.com", is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        display_name="Tenant Owner",
        password_hash=hash_password("right-password-1"),
        is_active=is_active,
    )


def make_membership(
    user: User, tenant: Tenant, *, role: MembershipRole = "owner"
) -> TenantMembership:
    return TenantMembership(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        is_active=True,
    )


def make_tenant() -> Tenant:
    return Tenant(id=uuid.uuid4(), name="Acme", slug="acme-1234abcd")


def make_auth_session(user: User, *, expires_in: timedelta) -> AuthSession:
    now = datetime.now(UTC)
    return AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="a" * 64,
        created_at=now - timedelta(hours=1),
        expires_at=now + expires_in,
        last_used_at=now - timedelta(hours=1),
    )


async def test_register_creates_user_tenant_and_owner_membership() -> None:
    # Given a registration request without an explicit tenant name
    service = make_service()
    spy = SpySession()

    # When registration succeeds
    result = await service.register(
        as_session(spy),
        email="Owner@Example.com",
        password="sup3r-secret",
        display_name="陈然",
        tenant_name=None,
    )

    # Then one commit persists user, tenant, owner membership, and session atomically
    assert spy.commit_calls == 1
    assert spy.rollback_calls == 0
    added_types = {type(instance) for instance in spy.added}
    assert added_types == {User, Tenant, TenantMembership, AuthSession}
    assert result.user.email == "owner@example.com"
    assert result.membership is not None
    assert result.membership.role == "owner"
    assert result.membership.tenant_name == "陈然 的租户"
    assert result.membership.tenant_slug
    assert result.session.token
    session_row = next(instance for instance in spy.added if isinstance(instance, AuthSession))
    assert result.session.token not in session_row.token_hash
    assert result.session.expires_at > datetime.now(UTC)


async def test_register_uses_explicit_tenant_name() -> None:
    # Given a registration request with an explicit tenant name
    service = make_service()
    spy = SpySession()

    # When registration succeeds
    result = await service.register(
        as_session(spy),
        email="owner@example.com",
        password="sup3r-secret",
        display_name="陈然",
        tenant_name="Acme 科技",
    )

    # Then the tenant uses the requested name
    assert result.membership is not None
    assert result.membership.tenant_name == "Acme 科技"


async def test_register_duplicate_email_rolls_back_everything() -> None:
    # Given a database that rejects the user insert with a unique violation
    service = make_service()
    duplicate = IntegrityError("INSERT INTO users", {}, ValueError("duplicate key"))
    spy = SpySession(fail_on_flush=duplicate)

    # When registration is attempted
    with pytest.raises(DuplicateEmailError):
        _ = await service.register(
            as_session(spy),
            email="owner@example.com",
            password="sup3r-secret",
            display_name="陈然",
            tenant_name=None,
        )

    # Then the transaction is rolled back before any tenant is created
    assert spy.rollback_calls == 1
    assert spy.commit_calls == 0
    assert all(not isinstance(instance, Tenant) for instance in spy.added)


async def test_register_commit_failure_rolls_back_and_propagates() -> None:
    # Given a database failure at commit time
    service = make_service()
    outage = SQLAlchemyError("connection lost")
    spy = SpySession(fail_on_commit=outage)

    # When registration is attempted
    with pytest.raises(SQLAlchemyError):
        _ = await service.register(
            as_session(spy),
            email="owner@example.com",
            password="sup3r-secret",
            display_name="陈然",
            tenant_name=None,
        )

    # Then the transaction is rolled back so no partial state is observable
    assert spy.rollback_calls == 1


async def test_login_unknown_email_raises_invalid_credentials_after_dummy_verify(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given no user matches the email and a spy on password verification
    service = make_service()
    spy = SpySession(execute_results=[None])
    verify_calls: list[str] = []

    def spy_verify(*, password_hash: str, password: str) -> bool:
        del password
        verify_calls.append(password_hash)
        return False

    monkeypatch.setattr(auth_service, "verify_password", spy_verify)

    # When login is attempted
    with pytest.raises(InvalidCredentialsError):
        _ = await service.login(as_session(spy), email="ghost@example.com", password="whatever-123")

    # Then a dummy verification still runs to mitigate user-enumeration timing
    assert verify_calls == [DUMMY_PASSWORD_HASH]
    assert spy.commit_calls == 0


async def test_login_wrong_password_raises_invalid_credentials() -> None:
    # Given a registered user
    service = make_service()
    user = make_user()
    spy = SpySession(execute_results=[user])

    # When the password does not match
    with pytest.raises(InvalidCredentialsError):
        _ = await service.login(
            as_session(spy),
            email="owner@example.com",
            password="wrong-password-1",
        )

    # Then no session is created
    assert spy.commit_calls == 0


async def test_login_success_issues_session() -> None:
    # Given a registered user
    service = make_service()
    user = make_user()
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    spy = SpySession(execute_results=[user, membership, tenant])

    # When the correct credentials are supplied
    result = await service.login(
        as_session(spy),
        email="OWNER@example.com",
        password="right-password-1",
    )

    # Then a session row is persisted and identity views reflect the owner membership
    assert spy.commit_calls == 1
    assert isinstance(result, AuthResult)
    assert result.user.email == "owner@example.com"
    assert result.membership is not None
    assert result.membership.role == "owner"
    assert result.membership.tenant_slug == "acme-1234abcd"
    session_row = next(instance for instance in spy.added if isinstance(instance, AuthSession))
    assert result.session.token not in session_row.token_hash


async def test_login_inactive_user_raises_invalid_credentials() -> None:
    # Given a deactivated user with correct credentials
    service = make_service()
    user = make_user(is_active=False)
    spy = SpySession(execute_results=[user])

    # When login is attempted
    with pytest.raises(InvalidCredentialsError):
        _ = await service.login(
            as_session(spy),
            email="owner@example.com",
            password="right-password-1",
        )

    # Then the failure is indistinguishable from wrong credentials
    assert spy.commit_calls == 0


async def test_authenticate_returns_none_for_unknown_token() -> None:
    # Given no session row matches the token hash
    service = make_service()
    spy = SpySession(execute_results=[None])

    # When the token is authenticated
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the caller is anonymous
    assert result is None
    assert spy.commit_calls == 0


async def test_authenticate_returns_none_for_expired_session() -> None:
    # Given a session that expired in the past
    service = make_service()
    user = make_user()
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=-1))
    spy = SpySession(execute_results=[auth_session])

    # When the token is authenticated
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the caller is anonymous
    assert result is None
    assert spy.commit_calls == 0


async def test_authenticate_returns_identity_and_touches_last_used() -> None:
    # Given a valid session far from expiry
    service = make_service()
    user = make_user()
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=SESSION_TTL_SECONDS))
    previous_last_used = auth_session.last_used_at
    spy = SpySession(execute_results=[auth_session, user, membership, tenant])

    # When the token is authenticated
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the identity is resolved, usage is tracked, and no renewal happens
    assert result is not None
    assert result.user.email == "owner@example.com"
    assert result.membership is not None
    assert result.membership.role == "owner"
    assert not result.renewed
    assert auth_session.last_used_at > previous_last_used
    assert spy.commit_calls == 1


async def test_authenticate_renews_session_inside_renewal_window() -> None:
    # Given a session whose remaining lifetime is inside the renewal window
    service = make_service()
    user = make_user()
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=3600))
    spy = SpySession(execute_results=[auth_session, user, membership, tenant])

    # When the token is authenticated
    before = datetime.now(UTC)
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the expiry slides to now plus the full TTL and is persisted
    assert result is not None
    assert result.renewed
    assert result.expires_at >= before + timedelta(seconds=SESSION_TTL_SECONDS)
    assert spy.commit_calls == 1


async def test_authenticate_returns_none_for_inactive_user() -> None:
    # Given a valid session owned by a deactivated user
    service = make_service()
    user = make_user(is_active=False)
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=3600))
    spy = SpySession(execute_results=[auth_session, user])

    # When the token is authenticated
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the caller is anonymous
    assert result is None


async def test_authenticate_exposes_missing_membership() -> None:
    # Given a valid session whose user has no active membership
    service = make_service()
    user = make_user()
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=3600))
    spy = SpySession(execute_results=[auth_session, user, None])

    # When the token is authenticated
    result = await service.authenticate(as_session(spy), token="opaque-token")

    # Then the user is authenticated but has no membership view
    assert result is not None
    assert result.membership is None


async def test_logout_deletes_session_row() -> None:
    # Given an existing session row
    service = make_service()
    user = make_user()
    auth_session = make_auth_session(user, expires_in=timedelta(seconds=3600))
    spy = SpySession(execute_results=[auth_session])

    # When logout runs
    await service.logout(as_session(spy), token="opaque-token")

    # Then the session row is deleted and committed
    assert spy.deleted == [auth_session]
    assert spy.commit_calls == 1


async def test_logout_is_idempotent_for_unknown_token() -> None:
    # Given no session row matches the token
    service = make_service()
    spy = SpySession(execute_results=[None])

    # When logout runs
    await service.logout(as_session(spy), token="opaque-token")

    # Then nothing breaks and nothing is persisted
    assert spy.deleted == []


async def test_register_with_invite_joins_issuing_tenant(monkeypatch: MonkeyPatch) -> None:
    # Given a pending invitation for the registering email
    service = make_service()
    tenant = make_tenant()
    invitation = TenantInvitation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="invitee@example.com",
        token_hash="b" * 64,
        invited_by=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    async def fake_load_pending(_session: object, *, token: str) -> TenantInvitation:
        assert token == "raw-invite-token"
        return invitation

    monkeypatch.setattr(invitation_service, "load_pending_invitation", fake_load_pending)
    spy = SpySession(execute_results=[tenant])

    # When registration succeeds with the invite token
    result = await service.register(
        as_session(spy),
        email="Invitee@Example.com",
        password="sup3r-secret",
        display_name="受邀用户",
        tenant_name=None,
        invite_token="raw-invite-token",
    )

    # Then no tenant is created and the membership joins the issuing tenant as member
    assert spy.commit_calls == 1
    added_types = {type(instance) for instance in spy.added}
    assert added_types == {User, TenantMembership, AuthSession}
    membership = next(i for i in spy.added if isinstance(i, TenantMembership))
    assert membership.tenant_id == tenant.id
    assert membership.role == "member"
    assert result.membership is not None
    assert result.membership.role == "member"
    assert result.membership.tenant_id == tenant.id
    assert invitation.accepted_at is not None


async def test_register_with_invite_rejects_email_mismatch(monkeypatch: MonkeyPatch) -> None:
    # Given a pending invitation for another email
    service = make_service()
    invitation = TenantInvitation(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="invitee@example.com",
        token_hash="b" * 64,
        invited_by=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    async def fake_load_pending(_session: object, *, token: str) -> TenantInvitation:
        del token
        return invitation

    monkeypatch.setattr(invitation_service, "load_pending_invitation", fake_load_pending)
    spy = SpySession()

    # When registration uses a different email
    with pytest.raises(InvitationEmailMismatchError):
        _ = await service.register(
            as_session(spy),
            email="other@example.com",
            password="sup3r-secret",
            display_name="冒名用户",
            tenant_name=None,
            invite_token="raw-invite-token",
        )

    # Then no user is created
    assert spy.added == []
    assert spy.commit_calls == 0


async def test_register_with_invalid_invite_creates_nothing(monkeypatch: MonkeyPatch) -> None:
    # Given the invitation service rejecting the token
    service = make_service()

    async def fake_load_pending(_session: object, *, token: str) -> TenantInvitation:
        del token
        raise InvitationInvalidError

    monkeypatch.setattr(invitation_service, "load_pending_invitation", fake_load_pending)
    spy = SpySession()

    # When registration is attempted
    with pytest.raises(InvitationInvalidError):
        _ = await service.register(
            as_session(spy),
            email="invitee@example.com",
            password="sup3r-secret",
            display_name="受邀用户",
            tenant_name=None,
            invite_token="bad-token",
        )

    # Then no user is created
    assert spy.added == []


async def test_login_returns_mfa_pending_when_totp_enabled() -> None:
    # Given a user with MFA enabled
    service = make_service()
    user = make_user()
    user.totp_secret = "SECRET"
    user.totp_enabled_at = datetime.now(UTC)
    spy = SpySession(execute_results=[user])

    # When the correct credentials are supplied
    result = await service.login(
        as_session(spy),
        email="owner@example.com",
        password="right-password-1",
    )

    # Then a pending challenge is stored instead of a session
    assert isinstance(result, MfaPending)
    assert result.mfa_token
    assert result.expires_at > datetime.now(UTC)
    challenge = next(i for i in spy.added if isinstance(i, MfaChallenge))
    assert result.mfa_token not in challenge.token_hash
    assert challenge.attempts == 0
    assert all(not isinstance(i, AuthSession) for i in spy.added)
    assert spy.commit_calls == 1


async def test_complete_mfa_login_issues_session() -> None:
    # Given a user whose challenge was verified
    service = make_service()
    user = make_user()
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    spy = SpySession(execute_results=[membership, tenant])

    # When the login is completed
    result = await service.complete_mfa_login(as_session(spy), user=user)

    # Then a normal session is issued
    assert result.user.email == "owner@example.com"
    assert result.membership is not None
    assert result.membership.tenant_slug == "acme-1234abcd"
    assert result.session.token
    assert spy.commit_calls == 1


async def test_complete_mfa_login_without_membership_fails() -> None:
    # Given a user without an active membership
    service = make_service()
    spy = SpySession(execute_results=[None])

    # When the login is completed
    with pytest.raises(InvalidCredentialsError):
        _ = await service.complete_mfa_login(as_session(spy), user=make_user())


async def test_register_promotes_allowlisted_email_to_platform_admin() -> None:
    # Given an allowlisted platform admin email
    service = AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
        platform_admin_emails=frozenset({"admin@example.com"}),
    )
    spy = SpySession()

    # When the allowlisted email registers
    result = await service.register(
        as_session(spy),
        email="Admin@Example.com",
        password="sup3r-secret",
        display_name="平台管理员",
        tenant_name=None,
    )

    # Then the user is flagged as platform admin
    assert result.user.is_platform_admin
    user = next(i for i in spy.added if isinstance(i, User))
    assert user.is_platform_admin


async def test_register_does_not_promote_other_emails() -> None:
    # Given an allowlist that does not contain the registrant
    service = AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
        platform_admin_emails=frozenset({"admin@example.com"}),
    )
    spy = SpySession()

    # When a regular email registers
    result = await service.register(
        as_session(spy),
        email="owner@example.com",
        password="sup3r-secret",
        display_name="陈然",
        tenant_name=None,
    )

    # Then no platform admin rights are granted
    assert not result.user.is_platform_admin
    user = next(i for i in spy.added if isinstance(i, User))
    assert not user.is_platform_admin


async def test_login_promotes_allowlisted_email_to_platform_admin() -> None:
    # Given an existing user whose email is later allowlisted
    service = AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
        platform_admin_emails=frozenset({"admin@example.com"}),
    )
    user = make_user(email="admin@example.com")
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    spy = SpySession(execute_results=[user, membership, tenant])

    # When the user logs in
    result = await service.login(
        as_session(spy),
        email="admin@example.com",
        password="right-password-1",
    )

    # Then the promotion is persisted with the session
    assert isinstance(result, AuthResult)
    assert result.user.is_platform_admin
    assert user.is_platform_admin
    assert spy.commit_calls == 1


async def test_login_platform_admin_without_membership_gets_session() -> None:
    # Given a platform administrator who belongs to no tenant
    service = AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
        platform_admin_emails=frozenset({"admin@example.com"}),
    )
    user = make_user(email="admin@example.com")
    spy = SpySession(execute_results=[user, None])

    # When the admin logs in
    result = await service.login(
        as_session(spy),
        email="admin@example.com",
        password="right-password-1",
    )

    # Then a session is issued without any tenant context
    assert isinstance(result, AuthResult)
    assert result.user.is_platform_admin
    assert result.membership is None
    assert result.session.token
    assert spy.commit_calls == 1


async def test_login_non_admin_without_membership_fails() -> None:
    # Given a regular user without an active membership
    service = make_service()
    user = make_user()
    spy = SpySession(execute_results=[user, None])

    # When login is attempted
    with pytest.raises(InvalidCredentialsError):
        _ = await service.login(
            as_session(spy),
            email="owner@example.com",
            password="right-password-1",
        )


async def test_complete_mfa_login_platform_admin_without_membership_gets_session() -> None:
    # Given a platform administrator without a tenant whose challenge was verified
    service = make_service()
    user = make_user(email="admin@example.com")
    user.is_platform_admin = True
    spy = SpySession(execute_results=[None])

    # When the login is completed
    result = await service.complete_mfa_login(as_session(spy), user=user)

    # Then a session is issued without any tenant context
    assert result.membership is None
    assert result.session.token
    assert spy.commit_calls == 1


async def test_register_platform_admin_skips_tenant_creation() -> None:
    # Given an allowlisted platform admin email
    service = AuthService(
        session_ttl_seconds=SESSION_TTL_SECONDS,
        session_renewal_window_seconds=RENEWAL_WINDOW_SECONDS,
        platform_admin_emails=frozenset({"admin@example.com"}),
    )
    spy = SpySession()

    # When the admin registers
    result = await service.register(
        as_session(spy),
        email="admin@example.com",
        password="sup3r-secret",
        display_name="平台管理员",
        tenant_name=None,
    )

    # Then no tenant or membership is created for them
    assert result.membership is None
    added_types = {type(instance) for instance in spy.added}
    assert added_types == {User, AuthSession}


async def test_login_revokes_platform_admin_when_email_leaves_allowlist() -> None:
    # Given a user whose email was removed from the allowlist
    service = make_service()
    user = make_user(email="former-admin@example.com")
    user.is_platform_admin = True
    tenant = make_tenant()
    membership = make_membership(user, tenant)
    spy = SpySession(execute_results=[user, membership, tenant])

    # When the user logs in
    result = await service.login(
        as_session(spy),
        email="former-admin@example.com",
        password="right-password-1",
    )

    # Then the flag is revoked with the next authentication
    assert isinstance(result, AuthResult)
    assert not result.user.is_platform_admin
    assert not user.is_platform_admin


async def test_register_starts_trial_subscription_for_new_tenant(
    monkeypatch: MonkeyPatch,
) -> None:
    # Given a spy on the trial subscription hook
    service = make_service()
    trial_calls: list[uuid.UUID] = []

    async def fake_start_trial(_session: object, *, tenant_id: uuid.UUID) -> None:
        trial_calls.append(tenant_id)

    monkeypatch.setattr(usage_service, "start_trial_subscription", fake_start_trial)
    spy = SpySession()

    # When registration creates a new tenant
    result = await service.register(
        as_session(spy),
        email="owner@example.com",
        password="sup3r-secret",
        display_name="陈然",
        tenant_name=None,
    )

    # Then the trial subscription starts for that tenant inside the same transaction
    assert result.membership is not None
    assert trial_calls == [result.membership.tenant_id]
    assert spy.commit_calls == 1


async def test_register_with_invite_skips_trial_subscription(monkeypatch: MonkeyPatch) -> None:
    # Given a pending invitation and a spy on the trial subscription hook
    service = make_service()
    tenant = make_tenant()
    invitation = TenantInvitation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="invitee@example.com",
        token_hash="b" * 64,
        invited_by=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    async def fake_load_pending(_session: object, *, token: str) -> TenantInvitation:
        del token
        return invitation

    trial_calls: list[uuid.UUID] = []

    async def fake_start_trial(_session: object, *, tenant_id: uuid.UUID) -> None:
        trial_calls.append(tenant_id)

    monkeypatch.setattr(invitation_service, "load_pending_invitation", fake_load_pending)
    monkeypatch.setattr(usage_service, "start_trial_subscription", fake_start_trial)
    spy = SpySession(execute_results=[tenant])

    # When registration joins the issuing tenant
    _ = await service.register(
        as_session(spy),
        email="invitee@example.com",
        password="sup3r-secret",
        display_name="受邀用户",
        tenant_name=None,
        invite_token="raw-invite-token",
    )

    # Then no trial subscription is started
    assert trial_calls == []
