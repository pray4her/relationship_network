import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import invitation_service, tenant_context, usage_service
from relationship_network_api.models import (
    MEMBER_ROLE,
    OWNER_ROLE,
    AuthSession,
    MembershipRole,
    MfaChallenge,
    Tenant,
    TenantMembership,
    User,
)
from relationship_network_api.security import (
    DUMMY_PASSWORD_HASH,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)

_SLUG_SEPARATOR_RUN: Final = re.compile(r"[^a-z0-9]+")
_SLUG_RANDOM_LENGTH: Final = 8


@final
class DuplicateEmailError(Exception):
    """Raised when registration reuses an already registered email."""


@final
class InvalidCredentialsError(Exception):
    """Raised when login credentials do not authenticate, without revealing why."""


@final
@dataclass(frozen=True)
class UserView:
    """Public identity of a user."""

    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool = False


@final
@dataclass(frozen=True)
class MembershipView:
    """Tenant context granted by an active membership."""

    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: MembershipRole


@final
@dataclass(frozen=True)
class IssuedSession:
    """Freshly issued opaque session token and its expiry."""

    token: str
    expires_at: datetime


@final
@dataclass(frozen=True)
class AuthResult:
    """Outcome of a successful registration or login.

    Platform administrators without any tenant membership authenticate with a
    None membership; they never gain tenant access implicitly.
    """

    user: UserView
    membership: MembershipView | None
    session: IssuedSession


@final
@dataclass(frozen=True)
class MfaPending:
    """Login outcome when the account requires a second factor."""

    user: UserView
    mfa_token: str
    expires_at: datetime


@final
@dataclass(frozen=True)
class Authentication:
    """Resolved caller identity for an authenticated request."""

    user: UserView
    membership: MembershipView | None
    expires_at: datetime
    renewed: bool


def normalize_email(email: str) -> str:
    """Normalize an email for storage and lookup."""
    return email.strip().lower()


def default_tenant_name(display_name: str) -> str:
    """Derive the default tenant name from the owner's display name."""
    return f"{display_name} 的租户"


def generate_tenant_slug(name: str) -> str:
    """Build a unique URL-safe slug from a tenant name."""
    base = _SLUG_SEPARATOR_RUN.sub("-", name.lower()).strip("-") or "tenant"
    return f"{base[:100]}-{uuid.uuid4().hex[:_SLUG_RANDOM_LENGTH]}"


@final
class AuthService:
    """Registration, login, logout, and sliding session renewal."""

    def __init__(
        self,
        *,
        session_ttl_seconds: int,
        session_renewal_window_seconds: int,
        mfa_challenge_ttl_seconds: int = 300,
        platform_admin_emails: frozenset[str] | None = None,
    ) -> None:
        self._session_ttl = timedelta(seconds=session_ttl_seconds)
        self._renewal_window = timedelta(seconds=session_renewal_window_seconds)
        self._mfa_challenge_ttl = timedelta(seconds=mfa_challenge_ttl_seconds)
        self._platform_admin_emails = (
            platform_admin_emails if platform_admin_emails is not None else frozenset()
        )

    async def register(  # noqa: PLR0913
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_name: str | None,
        invite_token: str | None = None,
    ) -> AuthResult:
        """Create user, tenant, owner membership, and session in one transaction.

        With an invite token, no tenant is created: the user joins the issuing
        tenant as a plain member and the invitation is marked accepted. A newly
        created tenant also gets its trial subscription in the same transaction.
        """
        invitation = None
        if invite_token is not None:
            invitation = await invitation_service.load_pending_invitation(
                session,
                token=invite_token,
            )
            if invitation.email != normalize_email(email):
                raise invitation_service.InvitationEmailMismatchError
        user = User(
            id=uuid.uuid4(),
            email=normalize_email(email),
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError as error:
            await session.rollback()
            raise DuplicateEmailError from error
        self._sync_platform_admin_grant(user)

        membership: TenantMembership | None
        tenant: Tenant | None
        if invitation is not None:
            await tenant_context.set_user_context(session, user.id)
            tenant = await self._load_tenant(session, invitation.tenant_id)
            membership = TenantMembership(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=user.id,
                role=MEMBER_ROLE,
                is_active=True,
            )
            session.add(membership)
            invitation.accepted_at = datetime.now(UTC)
        elif user.is_platform_admin:
            # Platform administrators do not automatically become tenant members.
            membership = None
            tenant = None
        else:
            resolved_tenant_name = tenant_name or default_tenant_name(display_name)
            tenant = Tenant(
                id=uuid.uuid4(),
                name=resolved_tenant_name,
                slug=generate_tenant_slug(resolved_tenant_name),
            )
            session.add(tenant)
            await tenant_context.set_tenant_context(session, tenant.id)
            membership = TenantMembership(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=user.id,
                role=OWNER_ROLE,
                is_active=True,
            )
            session.add(membership)
            _ = await usage_service.start_trial_subscription(session, tenant_id=tenant.id)
        return await self._issue_session_result(session, user, membership, tenant)

    async def login(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> AuthResult | MfaPending:
        """Authenticate credentials and issue a session, never revealing the failure cause.

        Accounts with MFA enabled get a pending challenge instead of a session;
        the challenge must be completed through the MFA verify endpoint.
        """
        result = await session.execute(select(User).where(User.email == normalize_email(email)))
        user = result.scalar_one_or_none()
        if user is None:
            _ = verify_password(password_hash=DUMMY_PASSWORD_HASH, password=password)
            raise InvalidCredentialsError
        if not verify_password(password_hash=user.password_hash, password=password):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InvalidCredentialsError
        self._sync_platform_admin_grant(user)

        if user.totp_enabled_at is not None:
            now = datetime.now(UTC)
            mfa_token = generate_session_token()
            challenge = MfaChallenge(
                id=uuid.uuid4(),
                user_id=user.id,
                token_hash=hash_session_token(mfa_token),
                attempts=0,
                created_at=now,
                expires_at=now + self._mfa_challenge_ttl,
            )
            session.add(challenge)
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                raise
            return MfaPending(
                user=_user_view(user),
                mfa_token=mfa_token,
                expires_at=challenge.expires_at,
            )

        await tenant_context.set_user_context(session, user.id)
        membership, tenant = await self._load_membership(session, user.id)
        if (membership is None or tenant is None) and not user.is_platform_admin:
            raise InvalidCredentialsError
        return await self._issue_session_result(session, user, membership, tenant)

    async def complete_mfa_login(self, session: AsyncSession, *, user: User) -> AuthResult:
        """Issue a session for a user whose MFA challenge was verified."""
        await tenant_context.set_user_context(session, user.id)
        membership, tenant = await self._load_membership(session, user.id)
        if (membership is None or tenant is None) and not user.is_platform_admin:
            raise InvalidCredentialsError
        return await self._issue_session_result(session, user, membership, tenant)

    async def logout(self, session: AsyncSession, *, token: str | None) -> None:
        """Delete the session row for the token; idempotent for unknown tokens."""
        if token is None:
            return
        result = await session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        auth_session = result.scalar_one_or_none()
        if auth_session is None:
            return
        await session.delete(auth_session)
        await session.commit()

    async def authenticate(self, session: AsyncSession, *, token: str) -> Authentication | None:
        """Resolve the caller identity, sliding the session expiry forward when due."""
        result = await session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        auth_session = result.scalar_one_or_none()
        if auth_session is None:
            return None
        now = datetime.now(UTC)
        if auth_session.expires_at <= now:
            return None
        result = await session.execute(select(User).where(User.id == auth_session.user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None

        await tenant_context.set_user_context(session, user.id)
        membership, tenant = await self._load_membership(session, user.id)

        auth_session.last_used_at = now
        renewed = auth_session.expires_at - now < self._renewal_window
        if renewed:
            auth_session.expires_at = now + self._session_ttl
        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise
        return Authentication(
            user=_user_view(user),
            membership=(
                _membership_view(membership, tenant)
                if membership is not None and tenant is not None
                else None
            ),
            expires_at=auth_session.expires_at,
            renewed=renewed,
        )

    def _build_session(self, user: User) -> tuple[str, AuthSession]:
        now = datetime.now(UTC)
        token = generate_session_token()
        return token, AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(token),
            created_at=now,
            expires_at=now + self._session_ttl,
            last_used_at=now,
        )

    async def _issue_session_result(
        self,
        session: AsyncSession,
        user: User,
        membership: TenantMembership | None,
        tenant: Tenant | None,
    ) -> AuthResult:
        """Persist a fresh session and render the auth result in one transaction."""
        token, auth_session = self._build_session(user)
        session.add(auth_session)
        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise
        return AuthResult(
            user=_user_view(user),
            membership=(
                _membership_view(membership, tenant)
                if membership is not None and tenant is not None
                else None
            ),
            session=IssuedSession(token=token, expires_at=auth_session.expires_at),
        )

    def _sync_platform_admin_grant(self, user: User) -> None:
        """Align the platform admin flag with the env allowlist on each auth event.

        The allowlist is the single source of truth: emails added to it gain
        the flag here, and emails removed from it lose the flag on their next
        registration or login. The flag is never set through any API.
        """
        user.is_platform_admin = user.email in self._platform_admin_emails

    async def _load_membership(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> tuple[TenantMembership | None, Tenant | None]:
        result = await session.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.is_active,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            return None, None
        return membership, await self._load_tenant(session, membership.tenant_id)

    async def _load_tenant(self, session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            raise InvalidCredentialsError
        return tenant


def _user_view(user: User) -> UserView:
    return UserView(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_platform_admin=user.is_platform_admin,
    )


def _membership_view(membership: TenantMembership, tenant: Tenant) -> MembershipView:
    return MembershipView(
        membership_id=membership.id,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        role=membership.role,
    )
