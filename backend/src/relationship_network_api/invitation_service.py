import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, final

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import tenant_context
from relationship_network_api.models import (
    MEMBER_ROLE,
    MembershipRole,
    Tenant,
    TenantInvitation,
    TenantMembership,
    User,
)
from relationship_network_api.security import generate_session_token, hash_session_token

InvitationStatus = Literal["pending", "accepted", "revoked", "expired"]
"""Lifecycle state of an invitation, computed from its timestamps."""

EMAIL_ALREADY_MEMBER_DETAIL: Final = "email_already_member"
INVITATION_ALREADY_PENDING_DETAIL: Final = "invitation_already_pending"
INVITATION_NOT_FOUND_DETAIL: Final = "invitation_not_found"
INVITATION_ALREADY_ACCEPTED_DETAIL: Final = "invitation_already_accepted"
INVITATION_INVALID_DETAIL: Final = "invitation_invalid"
INVITATION_EMAIL_MISMATCH_DETAIL: Final = "invitation_email_mismatch"
ALREADY_IN_TENANT_DETAIL: Final = "already_in_tenant"


@final
class EmailAlreadyMemberError(Exception):
    """Raised when the invited email already holds an active membership in the tenant."""


@final
class InvitationAlreadyPendingError(Exception):
    """Raised when a pending invitation already exists for the email in the tenant."""


@final
class InvitationNotFoundError(Exception):
    """Raised when an invitation does not exist in the caller's tenant."""


@final
class InvitationAlreadyAcceptedError(Exception):
    """Raised when revoking an invitation that was already accepted."""


@final
class InvitationInvalidError(Exception):
    """Raised when an invitation token is unknown, expired, revoked, or used."""


@final
class InvitationEmailMismatchError(Exception):
    """Raised when the accepting user's email differs from the invited email."""


@final
class AlreadyInTenantError(Exception):
    """Raised when the accepting user already holds an active membership."""


@final
class UserNotFoundError(Exception):
    """Raised when the authenticated user no longer exists or is disabled."""


@final
@dataclass(frozen=True)
class InvitationView:
    """A tenant invitation with its computed lifecycle status."""

    id: uuid.UUID
    email: str
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


@final
@dataclass(frozen=True)
class CreatedInvitation:
    """A freshly created invitation together with its one-time raw token."""

    invitation: InvitationView
    token: str


@final
@dataclass(frozen=True)
class InvitationPreview:
    """Public, minimal view of a pending invitation."""

    email: str
    tenant_name: str
    expires_at: datetime


@final
@dataclass(frozen=True)
class AcceptedInvitation:
    """The membership granted by accepting an invitation."""

    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: MembershipRole


def _normalize_email(email: str) -> str:
    """Normalize an email for storage and lookup."""
    return email.strip().lower()


def invitation_status(invitation: TenantInvitation, *, now: datetime) -> InvitationStatus:
    """Compute the lifecycle status of an invitation at a point in time."""
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.expires_at <= now:
        return "expired"
    return "pending"


async def create_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    invited_by: uuid.UUID,
    invitation_ttl_seconds: int,
) -> CreatedInvitation:
    """Create a single-use invitation; the raw token is returned only here."""
    normalized = _normalize_email(email)
    now = datetime.now(UTC)
    membership = (
        await session.execute(
            select(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
                User.email == normalized,
            )
        )
    ).scalar_one_or_none()
    if membership is not None:
        raise EmailAlreadyMemberError
    pending = (
        await session.execute(
            select(TenantInvitation).where(
                TenantInvitation.tenant_id == tenant_id,
                TenantInvitation.email == normalized,
                TenantInvitation.accepted_at.is_(None),
                TenantInvitation.revoked_at.is_(None),
                TenantInvitation.expires_at > now,
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise InvitationAlreadyPendingError

    token = generate_session_token()
    invitation = TenantInvitation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=normalized,
        token_hash=hash_session_token(token),
        invited_by=invited_by,
        expires_at=now + timedelta(seconds=invitation_ttl_seconds),
    )
    session.add(invitation)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    return CreatedInvitation(invitation=_invitation_view(invitation, now=now), token=token)


async def list_invitations(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[InvitationView]:
    """List all invitations of the tenant, newest first."""
    result = await session.execute(
        select(TenantInvitation)
        .where(TenantInvitation.tenant_id == tenant_id)
        .order_by(TenantInvitation.created_at.desc())
    )
    now = datetime.now(UTC)
    return [_invitation_view(invitation, now=now) for invitation in result.scalars().all()]


async def revoke_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    invitation_id: uuid.UUID,
) -> InvitationView:
    """Revoke a pending invitation; idempotent when already revoked."""
    invitation = (
        await session.execute(
            select(TenantInvitation).where(
                TenantInvitation.id == invitation_id,
                TenantInvitation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise InvitationNotFoundError
    if invitation.accepted_at is not None:
        raise InvitationAlreadyAcceptedError
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise
    return _invitation_view(invitation, now=datetime.now(UTC))


async def preview_invitation(session: AsyncSession, *, token: str) -> InvitationPreview:
    """Resolve a pending invitation by its raw token for the public accept page."""
    invitation = await load_pending_invitation(session, token=token)
    tenant = await _load_tenant(session, invitation.tenant_id)
    return InvitationPreview(
        email=invitation.email,
        tenant_name=tenant.name,
        expires_at=invitation.expires_at,
    )


async def accept_invitation(
    session: AsyncSession,
    *,
    token: str,
    user: User,
) -> AcceptedInvitation:
    """Accept a pending invitation, joining the issuing tenant as a member."""
    invitation = await load_pending_invitation(session, token=token)
    if _normalize_email(user.email) != invitation.email:
        raise InvitationEmailMismatchError
    # Pin the user context before reading memberships: row level security only
    # exposes the caller's own membership rows when app.user_id is set.
    await tenant_context.set_user_context(session, user.id)
    membership = (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.is_active,
            )
        )
    ).scalar_one_or_none()
    if membership is not None:
        raise AlreadyInTenantError

    tenant = await _load_tenant(session, invitation.tenant_id)
    session.add(
        TenantMembership(
            id=uuid.uuid4(),
            tenant_id=invitation.tenant_id,
            user_id=user.id,
            role=MEMBER_ROLE,
            is_active=True,
        )
    )
    invitation.accepted_at = datetime.now(UTC)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    return AcceptedInvitation(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        role=MEMBER_ROLE,
    )


async def load_user(session: AsyncSession, *, user_id: uuid.UUID) -> User:
    """Load the authenticated ORM user, refusing missing or disabled accounts."""
    result = await session.execute(select(User).where(User.id == user_id, User.is_active))
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError
    return user


async def load_pending_invitation(session: AsyncSession, *, token: str) -> TenantInvitation:
    """Load a pending invitation by its raw token, refusing any other state."""
    await tenant_context.set_invitation_token_context(session, hash_session_token(token))
    invitation = (
        await session.execute(
            select(TenantInvitation).where(TenantInvitation.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()
    if invitation is None or invitation_status(invitation, now=datetime.now(UTC)) != "pending":
        raise InvitationInvalidError
    return invitation


async def _load_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise InvitationInvalidError
    return tenant


def _invitation_view(invitation: TenantInvitation, *, now: datetime) -> InvitationView:
    return InvitationView(
        id=invitation.id,
        email=invitation.email,
        status=invitation_status(invitation, now=now),
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        created_at=invitation.created_at,
    )
