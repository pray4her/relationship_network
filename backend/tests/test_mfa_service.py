import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast, final

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context
from relationship_network_api.mfa_service import (
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeInvalidError,
    MfaNotEnabledError,
    MfaRequiredByTenantError,
    MfaSetupRequiredError,
    complete_challenge,
    disable,
    enable,
    generate_recovery_code,
    hash_recovery_code,
    set_tenant_mfa_policy,
    start_setup,
    status,
)
from relationship_network_api.models import (
    MfaChallenge,
    MfaRecoveryCode,
    Tenant,
    User,
)
from relationship_network_api.security import (
    generate_totp_secret,
    hash_session_token,
    totp_code,
)

pytestmark = pytest.mark.anyio

USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@final
class FakeResult:
    def __init__(self, *, scalar: object = None, count: int = 0) -> None:
        self._scalar = scalar
        self._count = count

    def scalar_one_or_none(self) -> object:
        return self._scalar

    def scalar_one(self) -> object:
        return self._scalar if self._scalar is not None else self._count


@final
class SpySession:
    def __init__(self, results: list[FakeResult]) -> None:
        self._results = list(results)
        self.added: list[object] = []
        self.deleted_statements = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def add_all(self, instances: Iterable[object]) -> None:
        self.added.extend(instances)

    async def execute(self, _statement: object) -> FakeResult:
        if not self._results:
            self.deleted_statements += 1
            return FakeResult()
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

    monkeypatch.setattr(tenant_context, "set_user_context", _noop)


def make_user(
    *,
    totp_secret: str | None = None,
    mfa_enabled: bool = False,
) -> User:
    return User(
        id=USER_ID,
        email="member@example.com",
        display_name="Tenant Member",
        password_hash="hash",
        is_active=True,
        totp_secret=totp_secret,
        totp_enabled_at=datetime.now(UTC) if mfa_enabled else None,
    )


def make_challenge(*, user: User, **overrides: object) -> MfaChallenge:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "token_hash": hash_session_token("raw-mfa-token"),
        "attempts": 0,
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "used_at": None,
    }
    values.update(overrides)
    return MfaChallenge(**values)  # type: ignore[arg-type]


def current_code(secret: str) -> str:
    return totp_code(secret, at_time=int(datetime.now(UTC).timestamp()))


def test_recovery_code_format_and_hash_normalization() -> None:
    # Given a generated recovery code
    code = generate_recovery_code()

    # Then it matches the pinned format and hashes case/separator insensitively
    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){2}", code)
    assert hash_recovery_code(code) == hash_recovery_code(code.lower().replace("-", " "))
    assert hash_recovery_code(code) != hash_recovery_code(generate_recovery_code())


async def test_start_setup_stores_pending_secret() -> None:
    # Given a user without MFA
    user = make_user()
    spy = SpySession([FakeResult(scalar=user)])

    # When setup starts
    setup = await start_setup(as_session(spy), user_id=USER_ID)

    # Then the secret is stored pending and the otpauth URL carries it
    assert user.totp_secret == setup.secret
    assert setup.secret in setup.otpauth_url
    assert setup.otpauth_url.startswith("otpauth://totp/RelationshipNetwork:member%40example.com")
    assert "issuer=RelationshipNetwork" in setup.otpauth_url
    assert user.totp_enabled_at is None
    assert spy.commit_calls == 1


async def test_start_setup_rejects_already_enabled() -> None:
    # Given a user with MFA enabled
    spy = SpySession([FakeResult(scalar=make_user(totp_secret="S", mfa_enabled=True))])

    # When setup starts again
    with pytest.raises(MfaAlreadyEnabledError):
        _ = await start_setup(as_session(spy), user_id=USER_ID)


async def test_enable_issues_recovery_codes_once() -> None:
    # Given a user with a pending TOTP secret
    secret = generate_totp_secret()
    user = make_user(totp_secret=secret)
    spy = SpySession([FakeResult(scalar=user)])

    # When a valid code enables MFA
    codes = await enable(as_session(spy), user_id=USER_ID, code=current_code(secret))

    # Then MFA is enabled and ten hashed recovery codes are stored
    assert user.totp_enabled_at is not None
    assert len(codes) == 10
    stored = [entry for entry in spy.added if isinstance(entry, MfaRecoveryCode)]
    assert len(stored) == 10
    pairs = list(zip(stored, codes, strict=True))
    assert all(entry.code_hash == hash_recovery_code(code) for entry, code in pairs)
    assert all(code not in entry.code_hash for entry, code in pairs)
    assert spy.commit_calls == 1


async def test_enable_requires_pending_secret() -> None:
    # Given a user without a pending secret
    spy = SpySession([FakeResult(scalar=make_user())])

    # When enabling is attempted
    with pytest.raises(MfaNotEnabledError):
        _ = await enable(as_session(spy), user_id=USER_ID, code="123456")


async def test_enable_rejects_wrong_code() -> None:
    # Given a user with a pending secret
    spy = SpySession([FakeResult(scalar=make_user(totp_secret=generate_totp_secret()))])

    # When an invalid code is submitted
    with pytest.raises(InvalidMfaCodeError):
        _ = await enable(as_session(spy), user_id=USER_ID, code="000000")


async def test_disable_clears_secret_and_codes() -> None:
    # Given a user with MFA enabled and no enforcing tenant
    secret = generate_totp_secret()
    user = make_user(totp_secret=secret, mfa_enabled=True)
    spy = SpySession([FakeResult(scalar=user), FakeResult(count=0)])

    # When a valid code disables MFA
    await disable(as_session(spy), user_id=USER_ID, code=current_code(secret))

    # Then the secret is cleared
    assert user.totp_secret is None
    assert user.totp_enabled_at is None
    assert spy.commit_calls == 1


async def test_disable_blocked_by_tenant_policy() -> None:
    # Given a user with MFA enabled whose tenant enforces MFA
    secret = generate_totp_secret()
    spy = SpySession(
        [
            FakeResult(scalar=make_user(totp_secret=secret, mfa_enabled=True)),
            FakeResult(count=1),
        ]
    )

    # When disabling is attempted
    with pytest.raises(MfaRequiredByTenantError):
        await disable(as_session(spy), user_id=USER_ID, code=current_code(secret))


async def test_disable_rejects_wrong_code() -> None:
    # Given a user with MFA enabled
    secret = generate_totp_secret()
    spy = SpySession([FakeResult(scalar=make_user(totp_secret=secret, mfa_enabled=True))])

    # When an invalid code is submitted
    with pytest.raises(InvalidMfaCodeError):
        await disable(as_session(spy), user_id=USER_ID, code="000000")


async def test_status_reports_enabled_and_remaining_codes() -> None:
    # Given a user with MFA enabled and three unused recovery codes
    user = make_user(totp_secret="S", mfa_enabled=True)
    spy = SpySession([FakeResult(scalar=user), FakeResult(count=3)])

    # When the status is read
    mfa_status = await status(as_session(spy), user_id=USER_ID)

    # Then both fields are reported
    assert mfa_status.enabled
    assert mfa_status.recovery_codes_remaining == 3


async def test_complete_challenge_with_valid_totp() -> None:
    # Given a pending challenge for a user with MFA enabled
    secret = generate_totp_secret()
    user = make_user(totp_secret=secret, mfa_enabled=True)
    challenge = make_challenge(user=user)
    spy = SpySession([FakeResult(scalar=challenge), FakeResult(scalar=user)])

    # When the correct code is submitted
    resolved = await complete_challenge(
        as_session(spy),
        token="raw-mfa-token",
        code=current_code(secret),
        recovery_code=None,
    )

    # Then the challenge is consumed and the user resolved
    assert resolved is user
    assert challenge.used_at is not None
    assert spy.commit_calls == 1


async def test_complete_challenge_wrong_code_counts_attempt() -> None:
    # Given a pending challenge
    user = make_user(totp_secret=generate_totp_secret(), mfa_enabled=True)
    challenge = make_challenge(user=user)
    spy = SpySession([FakeResult(scalar=challenge), FakeResult(scalar=user)])

    # When a wrong code is submitted
    with pytest.raises(InvalidMfaCodeError):
        _ = await complete_challenge(
            as_session(spy),
            token="raw-mfa-token",
            code="000000",
            recovery_code=None,
        )

    # Then the failed attempt is persisted
    assert challenge.attempts == 1
    assert challenge.used_at is None
    assert spy.commit_calls == 1


async def test_complete_challenge_with_recovery_code_marks_it_used() -> None:
    # Given a pending challenge and an unused recovery code
    user = make_user(totp_secret=generate_totp_secret(), mfa_enabled=True)
    challenge = make_challenge(user=user)
    recovery = MfaRecoveryCode(
        id=uuid.uuid4(),
        user_id=user.id,
        code_hash=hash_recovery_code("AAAA-BBBB-CCCC"),
    )
    spy = SpySession(
        [
            FakeResult(scalar=challenge),
            FakeResult(scalar=user),
            FakeResult(scalar=recovery),
        ]
    )

    # When the recovery code is submitted
    resolved = await complete_challenge(
        as_session(spy),
        token="raw-mfa-token",
        code=None,
        recovery_code="aaaa bbbb cccc",
    )

    # Then both the code and the challenge are consumed
    assert resolved is user
    assert recovery.used_at is not None
    assert challenge.used_at is not None


async def test_complete_challenge_unknown_recovery_code_counts_attempt() -> None:
    # Given a pending challenge without a matching recovery code
    user = make_user(totp_secret="S", mfa_enabled=True)
    challenge = make_challenge(user=user)
    spy = SpySession([FakeResult(scalar=challenge), FakeResult(scalar=user), FakeResult()])

    # When an unknown recovery code is submitted
    with pytest.raises(InvalidMfaCodeError):
        _ = await complete_challenge(
            as_session(spy),
            token="raw-mfa-token",
            code=None,
            recovery_code="XXXX-YYYY-ZZZZ",
        )

    # Then the failed attempt is persisted
    assert challenge.attempts == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"used_at": datetime.now(UTC)},
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)},
        {"attempts": 5},
    ],
    ids=["used", "expired", "exhausted"],
)
async def test_complete_challenge_rejects_unusable_challenges(overrides: dict[str, object]) -> None:
    # Given a used, expired, or exhausted challenge
    user = make_user(totp_secret="S", mfa_enabled=True)
    challenge = make_challenge(user=user, **overrides)
    spy = SpySession([FakeResult(scalar=challenge)])

    # When it is verified
    with pytest.raises(MfaChallengeInvalidError):
        _ = await complete_challenge(
            as_session(spy),
            token="raw-mfa-token",
            code="123456",
            recovery_code=None,
        )


async def test_complete_challenge_rejects_unknown_token() -> None:
    # Given no challenge for the token
    spy = SpySession([FakeResult()])

    # When it is verified
    with pytest.raises(MfaChallengeInvalidError):
        _ = await complete_challenge(
            as_session(spy),
            token="raw-mfa-token",
            code="123456",
            recovery_code=None,
        )


async def test_set_tenant_mfa_policy_enables_when_caller_has_mfa() -> None:
    # Given a caller with MFA enabled and an existing tenant
    tenant = Tenant(id=TENANT_ID, name="Acme 科技", slug="acme-1234abcd", mfa_required=False)
    spy = SpySession(
        [
            FakeResult(scalar=make_user(totp_secret="S", mfa_enabled=True)),
            FakeResult(scalar=tenant),
        ]
    )

    # When the policy is enabled
    view = await set_tenant_mfa_policy(
        as_session(spy),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        required=True,
    )

    # Then the tenant enforces MFA
    assert view.mfa_required
    assert tenant.mfa_required
    assert spy.commit_calls == 1


async def test_set_tenant_mfa_policy_requires_caller_mfa_to_enable() -> None:
    # Given a caller without MFA
    spy = SpySession([FakeResult(scalar=make_user())])

    # When the policy is enabled
    with pytest.raises(MfaSetupRequiredError):
        _ = await set_tenant_mfa_policy(
            as_session(spy),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            required=True,
        )


async def test_set_tenant_mfa_policy_disable_skips_caller_check() -> None:
    # Given a tenant enforcing MFA
    tenant = Tenant(id=TENANT_ID, name="Acme 科技", slug="acme-1234abcd", mfa_required=True)
    spy = SpySession([FakeResult(scalar=tenant)])

    # When the policy is disabled
    view = await set_tenant_mfa_policy(
        as_session(spy),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        required=False,
    )

    # Then enforcement is lifted without requiring caller MFA
    assert not view.mfa_required
