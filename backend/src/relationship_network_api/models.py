import uuid
from datetime import datetime
from typing import Final, Literal, final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

MembershipRole = Literal["owner", "member"]
"""Roles a tenant membership can hold; stored as lowercase strings."""

OWNER_ROLE: Final[MembershipRole] = "owner"
MEMBER_ROLE: Final[MembershipRole] = "member"

TenantStatus = Literal["active", "suspended"]
"""Lifecycle states a tenant can be in; stored as lowercase strings."""

TENANT_STATUS_ACTIVE: Final[TenantStatus] = "active"
TENANT_STATUS_SUSPENDED: Final[TenantStatus] = "suspended"

UsageMetric = Literal["owners", "companies", "active_jobs", "searches", "matches", "reports"]
"""Usage metrics a plan can cap; stored as lowercase strings."""

USAGE_METRICS: Final[tuple[UsageMetric, ...]] = (
    "owners",
    "companies",
    "active_jobs",
    "searches",
    "matches",
    "reports",
)
"""All usage metrics in canonical summary order."""

CONCURRENT_METRICS: Final[frozenset[UsageMetric]] = frozenset(
    {"owners", "companies", "active_jobs"}
)
"""Long-lived count limits; the other metrics reset per billing period."""

SubscriptionStatus = Literal["trialing", "active", "expired", "cancelled"]
"""Lifecycle states a tenant subscription can be in; stored as lowercase strings."""

OfflineOrderStatus = Literal["pending", "confirmed", "rejected"]
"""Review states an offline order can be in; stored as lowercase strings."""

PlanVersionStatus = Literal["draft", "published", "archived"]
"""Lifecycle states a plan version can be in; stored as lowercase strings."""

LedgerEntryType = Literal["reserve", "confirm", "release", "vacate"]
"""Usage ledger entry kinds; stored as lowercase strings."""

CompanyStatus = Literal["active", "archived"]
"""Lifecycle states a company can be in; stored as lowercase strings."""

COMPANY_STATUS_ACTIVE: Final[CompanyStatus] = "active"
COMPANY_STATUS_ARCHIVED: Final[CompanyStatus] = "archived"

DocumentScanStatus = Literal["clean", "rejected", "content_checked"]
"""Document content-scan outcomes; stored as lowercase strings."""

JobStatus = Literal["draft", "active", "closed", "archived"]
"""Lifecycle states a job posting can be in; stored as lowercase strings."""

JOB_STATUS_DRAFT: Final[JobStatus] = "draft"
JOB_STATUS_ACTIVE: Final[JobStatus] = "active"
JOB_STATUS_CLOSED: Final[JobStatus] = "closed"
JOB_STATUS_ARCHIVED: Final[JobStatus] = "archived"


class Base(DeclarativeBase):
    pass


@final
class ServiceMetadata(Base):
    __tablename__ = "service_metadata"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="ck_tenants_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    mfa_required: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    status: Mapped[TenantStatus] = mapped_column(
        String(20),
        server_default=TENANT_STATUS_ACTIVE,
        default=TENANT_STATUS_ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="ck_tenant_memberships_role"),
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[MembershipRole] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(200), server_default="", default="")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )


@final
class MembershipRoleAssignment(Base):
    __tablename__ = "membership_roles"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )


@final
class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@final
class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class MfaChallenge(Base):
    __tablename__ = "mfa_challenges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class PlatformAuditEvent(Base):
    """Append-only record of a sensitive platform administration operation."""

    __tablename__ = "platform_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(1000), server_default="", default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class PlanVersion(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_plan_versions_status",
        ),
        UniqueConstraint("plan_id", "version", name="uq_plan_versions_plan_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("plans.id"),
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[PlanVersionStatus] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        CheckConstraint("limit_value >= 0", name="ck_plan_entitlements_limit"),
        CheckConstraint(
            "metric IN ('owners', 'companies', 'active_jobs', 'searches', 'matches', 'reports')",
            name="ck_plan_entitlements_metric",
        ),
    )

    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("plan_versions.id"),
        primary_key=True,
    )
    metric: Mapped[UsageMetric] = mapped_column(String(30), primary_key=True)
    limit_value: Mapped[int] = mapped_column(Integer)


@final
class OfflineOrder(Base):
    """A tenant's offline payment order awaiting platform administrator review."""

    __tablename__ = "offline_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_offline_orders_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_offline_orders_tenant_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("plan_versions.id"),
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    payment_reference: Mapped[str] = mapped_column(Text)
    # Reserved for future online payment channels; only manual offline
    # collection ("offline") exists for now. Invoicing is deliberately out of
    # scope for the first iteration, so no invoice fields are modelled yet.
    payment_channel: Mapped[str] = mapped_column(
        String(20),
        server_default="offline",
        default="offline",
    )
    payer_note: Mapped[str] = mapped_column(Text, server_default="", default="")
    status: Mapped[OfflineOrderStatus] = mapped_column(
        String(20),
        server_default="pending",
        default="pending",
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, server_default="", default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('trialing', 'active', 'expired', 'cancelled')",
            name="ck_tenant_subscriptions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("plan_versions.id"),
    )
    status: Mapped[SubscriptionStatus] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    offline_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("offline_orders.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class Company(Base):
    """A recruiting client company owned by a tenant."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_companies_status",
        ),
        Index("ix_companies_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    profile_text: Mapped[str] = mapped_column(Text, server_default="", default="")
    status: Mapped[CompanyStatus] = mapped_column(
        String(20),
        server_default=COMPANY_STATUS_ACTIVE,
        default=COMPANY_STATUS_ACTIVE,
    )
    usage_reservation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@final
class CompanyDocument(Base):
    """A privately stored company profile document with extracted text."""

    __tablename__ = "company_documents"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_company_documents_byte_size"),
        CheckConstraint(
            "scan_status IN ('clean', 'rejected', 'content_checked')",
            name="ck_company_documents_scan_status",
        ),
        UniqueConstraint("storage_key", name="uq_company_documents_storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    extracted_text: Mapped[str] = mapped_column(Text, server_default="", default="")
    scan_status: Mapped[DocumentScanStatus] = mapped_column(
        String(30),
        server_default="content_checked",
        default="content_checked",
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class Job(Base):
    """A job posting owned by a tenant, attached to one company."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'closed', 'archived')",
            name="ck_jobs_status",
        ),
        Index("ix_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_jobs_tenant_company", "tenant_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    status: Mapped[JobStatus] = mapped_column(
        String(20),
        server_default=JOB_STATUS_DRAFT,
        default=JOB_STATUS_DRAFT,
    )
    usage_reservation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@final
class JobMaterial(Base):
    """A privately stored job posting material with extracted text."""

    __tablename__ = "job_materials"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_job_materials_byte_size"),
        CheckConstraint(
            "scan_status IN ('clean', 'rejected', 'content_checked')",
            name="ck_job_materials_scan_status",
        ),
        UniqueConstraint("storage_key", name="uq_job_materials_storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    extracted_text: Mapped[str] = mapped_column(Text, server_default="", default="")
    scan_status: Mapped[DocumentScanStatus] = mapped_column(
        String(30),
        server_default="content_checked",
        default="content_checked",
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class TenantAuditEvent(Base):
    """Append-only tenant business audit record."""

    __tablename__ = "tenant_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(1000), server_default="", default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


@final
class UsageLedgerEntry(Base):
    """Append-only usage accounting row; reservations settle via confirm/release/vacate."""

    __tablename__ = "usage_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "metric IN ('owners', 'companies', 'active_jobs', 'searches', 'matches', 'reports')",
            name="ck_usage_ledger_entries_metric",
        ),
        CheckConstraint("amount > 0", name="ck_usage_ledger_entries_amount"),
        CheckConstraint(
            "entry_type IN ('reserve', 'confirm', 'release', 'vacate')",
            name="ck_usage_ledger_entries_entry_type",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_usage_ledger_tenant_idempotency",
        ),
        UniqueConstraint(
            "reservation_id",
            "entry_type",
            name="uq_usage_ledger_reservation_type",
        ),
        Index("ix_usage_ledger_entries_tenant_metric", "tenant_id", "metric"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenant_subscriptions.id"),
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    metric: Mapped[UsageMetric] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(Integer)
    entry_type: Mapped[LedgerEntryType] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
