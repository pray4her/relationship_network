import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Final, cast, final

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api.auth_service import (
    Authentication,
    AuthResult,
    DuplicateEmailError,
    InvalidCredentialsError,
    IssuedSession,
    MembershipView,
    UserView,
)
from relationship_network_api.config import AppSettings
from relationship_network_api.deps import (
    SESSION_COOKIE_NAME,
    get_auth_service,
    get_authentication,
    get_db_session,
    get_settings,
)
from relationship_network_api.main import create_app
from relationship_network_api.models import MembershipRole
from relationship_network_api.routers.auth import RegisterRequest

SESSION_TTL_SECONDS: Final = 1209600
UNSET: Final = object()


@final
class FakeAuthService:
    def __init__(self) -> None:
        self.register_error: Exception | None = None
        self.login_error: Exception | None = None
        self.logout_tokens: list[str | None] = []
        self.registered_tenant_names: list[str | None] = []

    async def register(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_name: str | None,
    ) -> AuthResult:
        del session, password
        if self.register_error is not None:
            raise self.register_error
        self.registered_tenant_names.append(tenant_name)
        return make_auth_result(email=email, display_name=display_name)

    async def login(self, session: AsyncSession, *, email: str, password: str) -> AuthResult:
        del session, password
        if self.login_error is not None:
            raise self.login_error
        return make_auth_result(email=email, display_name="Tenant Owner")

    async def logout(self, session: AsyncSession, *, token: str | None) -> None:
        del session
        self.logout_tokens.append(token)


def make_settings() -> AppSettings:
    return cast(
        "AppSettings",
        cast(
            "object",
            SimpleNamespace(
                session_ttl_seconds=SESSION_TTL_SECONDS,
                session_renewal_window_seconds=86400,
                session_cookie_secure=False,
            ),
        ),
    )


def make_membership_view(*, role: MembershipRole = "owner") -> MembershipView:
    return MembershipView(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role=role,
    )


def make_auth_result(*, email: str, display_name: str) -> AuthResult:
    return AuthResult(
        user=UserView(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email=email,
            display_name=display_name,
        ),
        membership=make_membership_view(),
        session=IssuedSession(
            token="opaque-session-token",
            expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS),
        ),
    )


def make_authentication(*, renewed: bool = False, with_membership: bool = True) -> Authentication:
    return Authentication(
        user=UserView(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="owner@example.com",
            display_name="Tenant Owner",
        ),
        membership=make_membership_view() if with_membership else None,
        expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS),
        renewed=renewed,
    )


def make_client(
    *,
    service: FakeAuthService | None = None,
    authentication: Authentication | None | object = UNSET,
) -> TestClient:
    app = create_app(checks=())
    resolved_service = service if service is not None else FakeAuthService()
    settings = make_settings()

    def override_service() -> FakeAuthService:
        return resolved_service

    def override_settings() -> AppSettings:
        return settings

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_auth_service] = override_service
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db_session] = override_session
    if authentication is not UNSET:

        def override_authentication() -> Authentication | None:
            return cast("Authentication | None", authentication)

        app.dependency_overrides[get_authentication] = override_authentication
    return TestClient(app)


def register_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "owner@example.com",
        "password": "sup3r-secret",
        "display_name": "陈然",
        "tenant_name": None,
    }
    payload.update(overrides)
    return payload


def test_register_returns_created_identity_and_sets_session_cookie() -> None:
    # Given a registration endpoint backed by a working auth service
    client = make_client()

    # When a valid registration is submitted
    response = client.post("/auth/register", json=register_payload())

    # Then the contract returns the created identity with an owner role
    assert response.status_code == 201
    assert response.json() == {
        "user": {
            "id": "22222222-2222-2222-2222-222222222222",
            "email": "owner@example.com",
            "display_name": "陈然",
        },
        "tenant": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Acme 科技",
            "slug": "acme-1234abcd",
        },
        "role": "owner",
    }
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=opaque-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "samesite=lax" in cookie.lower()
    assert f"Max-Age={SESSION_TTL_SECONDS}" in cookie


def test_register_rejects_short_password() -> None:
    # Given a registration payload with a too-short password
    client = make_client()

    # When it is submitted
    response = client.post("/auth/register", json=register_payload(password="short"))

    # Then validation rejects it before the service runs
    assert response.status_code == 422


def test_register_rejects_malformed_email() -> None:
    # Given a registration payload with a malformed email
    client = make_client()

    # When it is submitted
    response = client.post("/auth/register", json=register_payload(email="not-an-email"))

    # Then validation rejects it before the service runs
    assert response.status_code == 422


@pytest.mark.parametrize(
    "email",
    ["zhangsan@qq.com", "lisi@163.com", "owner@gmail.com"],
)
def test_register_schema_accepts_free_mail_addresses(email: str) -> None:
    # Given a normal free-mail address
    # When the registration schema validates it
    request = RegisterRequest(
        email=email,
        password="sup3r-secret",
        display_name="陈然",
        tenant_name=None,
    )

    # Then registration is allowed without a corporate-domain restriction
    assert request.email == email


def test_register_duplicate_email_returns_conflict() -> None:
    # Given an auth service that reports a duplicate email
    service = FakeAuthService()
    service.register_error = DuplicateEmailError()
    client = make_client(service=service)

    # When registration is submitted
    response = client.post("/auth/register", json=register_payload())

    # Then the caller receives the pinned conflict contract
    assert response.status_code == 409
    assert response.json() == {"detail": "email_already_registered"}


def test_login_returns_identity_and_sets_session_cookie() -> None:
    # Given a login endpoint backed by a working auth service
    client = make_client()

    # When valid credentials are submitted
    response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "sup3r-secret"},
    )

    # Then the identity contract and session cookie match registration
    assert response.status_code == 200
    assert response.json()["role"] == "owner"
    assert f"{SESSION_COOKIE_NAME}=opaque-session-token" in response.headers["set-cookie"]


def test_login_invalid_credentials_returns_uniform_unauthorized() -> None:
    # Given an auth service that rejects the credentials
    service = FakeAuthService()
    service.login_error = InvalidCredentialsError()
    client = make_client(service=service)

    # When login is attempted
    response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )

    # Then the failure never reveals whether the email or the password was wrong
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


def test_logout_clears_session_and_cookie() -> None:
    # Given an authenticated caller holding a session cookie
    service = FakeAuthService()
    client = make_client(service=service)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When logout is requested
    response = client.post("/auth/logout")

    # Then the session is deleted server-side and the cookie expires immediately
    assert response.status_code == 204
    assert response.content == b""
    assert service.logout_tokens == ["opaque-session-token"]
    cleared = response.headers["set-cookie"]
    assert SESSION_COOKIE_NAME in cleared
    assert "Max-Age=0" in cleared


def test_logout_is_idempotent_without_cookie() -> None:
    # Given an anonymous caller
    service = FakeAuthService()
    client = make_client(service=service)

    # When logout is requested
    response = client.post("/auth/logout")

    # Then it still succeeds
    assert response.status_code == 204
    assert service.logout_tokens == [None]


def test_me_returns_current_identity() -> None:
    # Given an authenticated session
    client = make_client(authentication=make_authentication())
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the current identity is requested
    response = client.get("/auth/me")

    # Then the identity contract matches registration
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    assert response.json()["role"] == "owner"


def test_me_requires_authentication() -> None:
    # Given no valid session
    client = make_client(authentication=None)

    # When the current identity is requested
    response = client.get("/auth/me")

    # Then the caller is rejected with the pinned detail
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_me_refreshes_cookie_when_session_was_renewed() -> None:
    # Given a session that the sliding renewal just extended
    client = make_client(authentication=make_authentication(renewed=True))
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the current identity is requested
    response = client.get("/auth/me")

    # Then the cookie is re-set with the extended lifetime
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=opaque-session-token" in cookie
    assert f"Max-Age={SESSION_TTL_SECONDS}" in cookie


def test_me_without_membership_returns_forbidden() -> None:
    # Given an authenticated user whose membership was deactivated
    client = make_client(authentication=make_authentication(with_membership=False))
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session-token")

    # When the current identity is requested
    response = client.get("/auth/me")

    # Then access is forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "no_active_membership"}
