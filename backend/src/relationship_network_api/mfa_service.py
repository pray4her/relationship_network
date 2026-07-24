import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, final
from urllib.parse import quote, urlencode

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context
from relationship_network_api.models import (
    MfaChallenge,
    MfaRecoveryCode,
    Tenant,
    TenantMembership,
    User,
)
from relationship_network_api.security import (
    generate_totp_secret,
    hash_session_token,
    verify_totp,
)

MFA_ALREADY_ENABLED_DETAIL: Final = "mfa_already_enabled"
MFA_NOT_ENABLED_DETAIL: Final = "mfa_not_enabled"
INVALID_MFA_CODE_DETAIL: Final = "invalid_mfa_code"
MFA_REQUIRED_BY_TENANT_DETAIL: Final = "mfa_required_by_tenant"
MFA_SETUP_REQUIRED_DETAIL: Final = "mfa_setup_required"
MFA_CHALLENGE_INVALID_DETAIL: Final = "mfa_challenge_invalid"
TENANT_NOT_FOUND_DETAIL: Final = "tenant_not_found"

MFA_ISSUER: Final = "RelationshipNetwork"
RECOVERY_CODE_COUNT: Final = 10
MAX_CHALLENGE_ATTEMPTS: Final = 5
_RECOVERY_ALPHABET: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford-style alphabet without easily confused letters."""
_RECOVERY_GROUP_LENGTH: Final = 4
_RECOVERY_GROUP_COUNT: Final = 3


@final
class MfaAlreadyEnabledError(Exception):
    """Raised when TOTP setup is started for an account that already has MFA."""


@final
class MfaNotEnabledError(Exception):
    """Raised when an MFA operation requires an enabled or pending TOTP secret."""


@final
class InvalidMfaCodeError(Exception):
    """Raised when a TOTP or recovery code does not verify."""


@final
class MfaRequiredByTenantError(Exception):
    """Raised when disabling MFA while a tenant policy requires it."""


@final
class MfaSetupRequiredError(Exception):
    """Raised when enforcing a tenant MFA policy without having MFA enabled."""


@final
class MfaChallengeInvalidError(Exception):
    """Raised when a login MFA challenge is unknown, expired, used, or exhausted."""


@final
class TenantNotFoundError(Exception):
    """Raised when the caller's tenant no longer exists."""


@final
@dataclass(frozen=True)
class MfaSetupView:
    """Pending TOTP secret and its provisioning URL, shown once at setup."""

    secret: str
    otpauth_url: str


@final
@dataclass(frozen=True)
class MfaStatusView:
    """Current MFA enrollment state of a user."""

    enabled: bool
    recovery_codes_remaining: int


@final
@dataclass(frozen=True)
class TenantMfaPolicyView:
    """A tenant with its MFA enforcement policy."""

    id: uuid.UUID
    name: str
    slug: str
    mfa_required: bool


def build_otpauth_url(*, secret: str, email: str) -> str:
    """Build the otpauth provisioning URL scanned by authenticator apps."""
    label = f"{MFA_ISSUER}:{email}"
    query = urlencode({"secret": secret, "issuer": MFA_ISSUER})
    return f"otpauth://totp/{quote(label, safe=':')}?{query}"


def generate_recovery_code() -> str:
    """Generate a single-use recovery code formatted as XXXX-XXXX-XXXX."""
    groups = (
        "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_GROUP_LENGTH))
        for _ in range(_RECOVERY_GROUP_COUNT)
    )
    return "-".join(groups)


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage, normalizing case and separators."""
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def start_setup(session: AsyncSession, *, user_id: uuid.UUID) -> MfaSetupView:
    """Start TOTP enrollment, storing a pending secret until enable verifies it."""
    user = await load_user(session, user_id=user_id)
    if user.totp_enabled_at is not None:
        raise MfaAlreadyEnabledError
    secret = generate_totp_secret()
    user.totp_secret = secret
    await _commit(session)
    return MfaSetupView(
        secret=secret,
        otpauth_url=build_otpauth_url(secret=secret, email=user.email),
    )


async def enable(session: AsyncSession, *, user_id: uuid.UUID, code: str) -> list[str]:
    """Confirm TOTP enrollment and issue one-time recovery codes, shown only here."""
    user = await load_user(session, user_id=user_id)
    if user.totp_enabled_at is not None:
        raise MfaAlreadyEnabledError
    if user.totp_secret is None:
        raise MfaNotEnabledError
    if not verify_totp(user.totp_secret, code, at_time=_now_timestamp()):
        raise InvalidMfaCodeError
    user.totp_enabled_at = datetime.now(UTC)
    _ = await session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    session.add_all(
        MfaRecoveryCode(id=uuid.uuid4(), user_id=user.id, code_hash=hash_recovery_code(code))
        for code in codes
    )
    await _commit(session)
    return codes


async def disable(session: AsyncSession, *, user_id: uuid.UUID, code: str) -> None:
    """Disable TOTP after verifying a code, unless a tenant policy requires MFA."""
    user = await load_user(session, user_id=user_id)
    if user.totp_enabled_at is None or user.totp_secret is None:
        raise MfaNotEnabledError
    if not verify_totp(user.totp_secret, code, at_time=_now_timestamp()):
        raise InvalidMfaCodeError
    # Membership rows are only visible once the user context is pinned.
    await tenant_context.set_user_context(session, user.id)
    enforcing = (
        await session.execute(
            select(func.count())
            .select_from(TenantMembership)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                TenantMembership.user_id == user.id,
                TenantMembership.is_active,
                Tenant.mfa_required,
            )
        )
    ).scalar_one()
    if enforcing > 0:
        raise MfaRequiredByTenantError
    user.totp_secret = None
    user.totp_enabled_at = None
    _ = await session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    await _commit(session)


async def status(session: AsyncSession, *, user_id: uuid.UUID) -> MfaStatusView:
    """Report whether MFA is enabled and how many recovery codes remain."""
    user = await load_user(session, user_id=user_id)
    remaining = (
        await session.execute(
            select(func.count())
            .select_from(MfaRecoveryCode)
            .where(MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.used_at.is_(None))
        )
    ).scalar_one()
    return MfaStatusView(
        enabled=user.totp_enabled_at is not None,
        recovery_codes_remaining=int(remaining),
    )


async def complete_challenge(
    session: AsyncSession,
    *,
    token: str,
    code: str | None,
    recovery_code: str | None,
) -> User:
    """Verify a login MFA challenge with a TOTP or recovery code.

    Exactly one of code or recovery_code must be provided; the route schema
    enforces that before this runs.
    """
    challenge = (
        await session.execute(
            select(MfaChallenge).where(MfaChallenge.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        challenge is None
        or challenge.used_at is not None
        or challenge.expires_at <= now
        or challenge.attempts >= MAX_CHALLENGE_ATTEMPTS
    ):
        raise MfaChallengeInvalidError
    result = await session.execute(select(User).where(User.id == challenge.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise MfaChallengeInvalidError
    if code is not None:
        valid = user.totp_secret is not None and verify_totp(
            user.totp_secret,
            code,
            at_time=_now_timestamp(),
        )
        if not valid:
            await _register_failure(session, challenge)
            raise InvalidMfaCodeError
    elif recovery_code is not None:
        recovery = (
            await session.execute(
                select(MfaRecoveryCode).where(
                    MfaRecoveryCode.user_id == user.id,
                    MfaRecoveryCode.code_hash == hash_recovery_code(recovery_code),
                    MfaRecoveryCode.used_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if recovery is None:
            await _register_failure(session, challenge)
            raise InvalidMfaCodeError
        recovery.used_at = now
    challenge.used_at = now
    await _commit(session)
    return user


async def set_tenant_mfa_policy(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    required: bool,
) -> TenantMfaPolicyView:
    """Update the tenant MFA policy; enforcing it requires the caller to have MFA."""
    if required:
        user = await load_user(session, user_id=user_id)
        if user.totp_enabled_at is None:
            raise MfaSetupRequiredError
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise TenantNotFoundError
    tenant.mfa_required = required
    await _commit(session)
    return TenantMfaPolicyView(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        mfa_required=tenant.mfa_required,
    )


async def load_user(session: AsyncSession, *, user_id: uuid.UUID) -> User:
    """Load an active ORM user or refuse."""
    result = await session.execute(select(User).where(User.id == user_id, User.is_active))
    user = result.scalar_one_or_none()
    if user is None:
        raise MfaNotEnabledError
    return user


async def _register_failure(session: AsyncSession, challenge: MfaChallenge) -> None:
    challenge.attempts += 1
    await _commit(session)


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise


def _now_timestamp() -> int:
    return int(datetime.now(UTC).timestamp())
