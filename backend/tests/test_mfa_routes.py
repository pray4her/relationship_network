import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import mfa_service
from relationship_network_api.auth_service import (
    Authentication,
    AuthResult,
    IssuedSession,
    MembershipView,
    UserView,
)
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_auth_service,
    get_authentication,
    get_db_session,
    get_settings,
)
from relationship_network_api.main import create_app
from relationship_network_api.mfa_service import (
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeInvalidError,
    MfaNotEnabledError,
    MfaRequiredByTenantError,
    MfaRequiredForPlatformAdminError,
    MfaSetupView,
    MfaStatusView,
)
from relationship_network_api.models import User

USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SESSION_TTL_SECONDS = 1209600


def make_authentication() -> Authentication:
    return Authentication(
        user=UserView(id=USER_ID, email="member@example.com", display_name="Tenant Member"),
        membership=None,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        renewed=False,
    )


def make_user() -> User:
    return User(
        id=USER_ID,
        email="member@example.com",
        display_name="Tenant Member",
        password_hash="hash",
        is_active=True,
    )


def make_auth_result() -> AuthResult:
    return AuthResult(
        user=UserView(id=USER_ID, email="member@example.com", display_name="Tenant Member"),
        membership=MembershipView(
            membership_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            tenant_name="Acme 科技",
            tenant_slug="acme-1234abcd",
            role="member",
        ),
        session=IssuedSession(
            token="opaque-session-token",
            expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS),
        ),
    )


def make_client(authentication: Authentication | None) -> TestClient:
    app = create_app(checks=())

    def override_authentication() -> Authentication | None:
        return authentication

    def override_auth_service() -> object:
        return SimpleNamespace(complete_mfa_login=fake_complete_mfa_login)

    def override_settings() -> object:
        return SimpleNamespace(
            session_ttl_seconds=SESSION_TTL_SECONDS,
            session_cookie_secure=False,
        )

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    async def fake_complete_mfa_login(_session: object, *, user: User) -> AuthResult:
        assert user.id == USER_ID
        return make_auth_result()

    app.dependency_overrides[get_authentication] = override_authentication
    app.dependency_overrides[get_auth_service] = override_auth_service
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def test_mfa_setup_returns_secret_and_otpauth_url(monkeypatch: MonkeyPatch) -> None:
    # Given an authenticated user without MFA
    async def fake_start_setup(_session: object, *, user_id: uuid.UUID) -> MfaSetupView:
        assert user_id == USER_ID
        return MfaSetupView(
            secret="GEZDGNBVGY3TQOJQ",
            otpauth_url="otpauth://totp/RelationshipNetwork:member@example.com?secret=GEZDGNBVGY3TQOJQ&issuer=RelationshipNetwork",
        )

    monkeypatch.setattr(mfa_service, "start_setup", fake_start_setup)
    client = make_client(make_authentication())

    # When setup starts
    response = client.post("/auth/mfa/setup")

    # Then the secret and provisioning URL are returned
    assert response.status_code == 200
    assert response.json()["secret"] == "GEZDGNBVGY3TQOJQ"
    assert response.json()["otpauth_url"].startswith("otpauth://totp/")


def test_mfa_setup_conflict_when_already_enabled(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting MFA already enabled
    async def fake_start_setup(_session: object, **_kwargs: object) -> MfaSetupView:
        raise MfaAlreadyEnabledError

    monkeypatch.setattr(mfa_service, "start_setup", fake_start_setup)
    client = make_client(make_authentication())

    # When setup starts again
    response = client.post("/auth/mfa/setup")

    # Then the conflict is reported
    assert response.status_code == 409
    assert response.json() == {"detail": "mfa_already_enabled"}


def test_mfa_enable_returns_recovery_codes_once(monkeypatch: MonkeyPatch) -> None:
    # Given the service accepting the TOTP code
    async def fake_enable(
        _session: object,
        *,
        user_id: uuid.UUID,
        code: str,
    ) -> list[str]:
        assert user_id == USER_ID
        assert code == "123456"
        return ["AAAA-BBBB-CCCC", "DDDD-EEEE-FFFF"]

    monkeypatch.setattr(mfa_service, "enable", fake_enable)
    client = make_client(make_authentication())

    # When MFA is enabled
    response = client.post("/auth/mfa/enable", json={"code": "123456"})

    # Then the recovery codes are returned once
    assert response.status_code == 200
    assert response.json() == {"recovery_codes": ["AAAA-BBBB-CCCC", "DDDD-EEEE-FFFF"]}


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (MfaAlreadyEnabledError(), 409, "mfa_already_enabled"),
        (MfaNotEnabledError(), 409, "mfa_not_enabled"),
        (InvalidMfaCodeError(), 401, "invalid_mfa_code"),
    ],
)
def test_mfa_enable_maps_service_errors(
    monkeypatch: MonkeyPatch,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    # Given the service rejecting the enable
    async def fake_enable(_session: object, **_kwargs: object) -> list[str]:
        raise error

    monkeypatch.setattr(mfa_service, "enable", fake_enable)
    client = make_client(make_authentication())

    # When MFA is enabled
    response = client.post("/auth/mfa/enable", json={"code": "123456"})

    # Then the pinned error contract is returned
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_mfa_disable_returns_no_content(monkeypatch: MonkeyPatch) -> None:
    # Given the service accepting the disable
    async def fake_disable(_session: object, *, user_id: uuid.UUID, code: str) -> None:
        assert user_id == USER_ID
        assert code == "123456"

    monkeypatch.setattr(mfa_service, "disable", fake_disable)
    client = make_client(make_authentication())

    # When MFA is disabled
    response = client.post("/auth/mfa/disable", json={"code": "123456"})

    # Then no content is returned
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (MfaNotEnabledError(), 409, "mfa_not_enabled"),
        (InvalidMfaCodeError(), 401, "invalid_mfa_code"),
        (MfaRequiredByTenantError(), 409, "mfa_required_by_tenant"),
        (MfaRequiredForPlatformAdminError(), 409, "mfa_required_for_platform_admin"),
    ],
)
def test_mfa_disable_maps_service_errors(
    monkeypatch: MonkeyPatch,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    # Given the service rejecting the disable
    async def fake_disable(_session: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(mfa_service, "disable", fake_disable)
    client = make_client(make_authentication())

    # When MFA is disabled
    response = client.post("/auth/mfa/disable", json={"code": "123456"})

    # Then the pinned error contract is returned
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_mfa_status_returns_enrollment_state(monkeypatch: MonkeyPatch) -> None:
    # Given the service reporting an enabled MFA with recovery codes left
    async def fake_status(_session: object, *, user_id: uuid.UUID) -> MfaStatusView:
        assert user_id == USER_ID
        return MfaStatusView(enabled=True, recovery_codes_remaining=8)

    monkeypatch.setattr(mfa_service, "status", fake_status)
    client = make_client(make_authentication())

    # When the status is read
    response = client.get("/auth/mfa/status")

    # Then the enrollment state is returned
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "recovery_codes_remaining": 8}


def test_mfa_management_endpoints_require_authentication() -> None:
    # Given an anonymous caller
    client = make_client(None)

    # When any management endpoint is called
    responses = [
        client.post("/auth/mfa/setup"),
        client.post("/auth/mfa/enable", json={"code": "123456"}),
        client.post("/auth/mfa/disable", json={"code": "123456"}),
        client.get("/auth/mfa/status"),
    ]

    # Then the caller is rejected
    for response in responses:
        assert response.status_code == 401
        assert response.json() == {"detail": "not_authenticated"}


def test_mfa_verify_with_totp_issues_session(monkeypatch: MonkeyPatch) -> None:
    # Given the service accepting the challenge
    async def fake_complete_challenge(
        _session: object,
        *,
        token: str,
        code: str | None,
        recovery_code: str | None,
    ) -> User:
        assert token == "raw-mfa-token"
        assert code == "123456"
        assert recovery_code is None
        return make_user()

    monkeypatch.setattr(mfa_service, "complete_challenge", fake_complete_challenge)
    client = make_client(None)

    # When the challenge is verified
    response = client.post(
        "/auth/mfa/verify",
        json={"mfa_token": "raw-mfa-token", "code": "123456"},
    )

    # Then a session is issued like a normal login
    assert response.status_code == 200
    assert response.json()["role"] == "member"
    assert f"{SESSION_COOKIE_NAME}=opaque-session-token" in response.headers["set-cookie"]


def test_mfa_verify_with_recovery_code_issues_session(monkeypatch: MonkeyPatch) -> None:
    # Given the service accepting the recovery code
    async def fake_complete_challenge(
        _session: object,
        *,
        token: str,
        code: str | None,
        recovery_code: str | None,
    ) -> User:
        assert token == "raw-mfa-token"
        assert code is None
        assert recovery_code == "AAAA-BBBB-CCCC"
        return make_user()

    monkeypatch.setattr(mfa_service, "complete_challenge", fake_complete_challenge)
    client = make_client(None)

    # When the challenge is verified with a recovery code
    response = client.post(
        "/auth/mfa/verify",
        json={"mfa_token": "raw-mfa-token", "recovery_code": "AAAA-BBBB-CCCC"},
    )

    # Then a session is issued
    assert response.status_code == 200
    assert f"{SESSION_COOKIE_NAME}=opaque-session-token" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    "payload",
    [
        {"mfa_token": "raw-mfa-token"},
        {"mfa_token": "raw-mfa-token", "code": "123456", "recovery_code": "AAAA-BBBB-CCCC"},
    ],
    ids=["neither", "both"],
)
def test_mfa_verify_requires_exactly_one_factor(payload: dict[str, str]) -> None:
    # Given a verify payload with neither or both factors
    client = make_client(None)

    # When it is submitted
    response = client.post("/auth/mfa/verify", json=payload)

    # Then validation rejects it before the service runs
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (MfaChallengeInvalidError(), "mfa_challenge_invalid"),
        (InvalidMfaCodeError(), "invalid_mfa_code"),
    ],
)
def test_mfa_verify_maps_service_errors(
    monkeypatch: MonkeyPatch,
    error: Exception,
    expected_detail: str,
) -> None:
    # Given the service rejecting the challenge
    async def fake_complete_challenge(_session: object, **_kwargs: object) -> User:
        raise error

    monkeypatch.setattr(mfa_service, "complete_challenge", fake_complete_challenge)
    client = make_client(None)

    # When the challenge is verified
    response = client.post(
        "/auth/mfa/verify",
        json={"mfa_token": "raw-mfa-token", "code": "123456"},
    )

    # Then the pinned error contract is returned
    assert response.status_code == 401
    assert response.json() == {"detail": expected_detail}
