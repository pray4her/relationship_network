import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_billing_and_usage"
down_revision: str | None = "0005_platform_admin_and_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"

_TENANT_TABLES = ("tenant_subscriptions", "usage_ledger_entries")

_USAGE_METRIC_CHECK = (
    "metric IN ('owners', 'companies', 'active_jobs', 'searches', 'matches', 'reports')"
)

# Deterministic seed identifiers (uuid5) keep upgrade/downgrade cycles repeatable.
_TRIAL_PLAN_ID = uuid.uuid5(uuid.NAMESPACE_URL, "relationship-network/billing/trial/plan")
_TRIAL_PLAN_VERSION_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "relationship-network/billing/trial/plan-version"
)
_TRIAL_ENTITLEMENTS = (
    ("owners", 1),
    ("companies", 1),
    ("active_jobs", 2),
    ("searches", 20),
    ("matches", 3),
    ("reports", 1),
)


def upgrade() -> None:
    # Global plan catalog; published versions stay immutable so subscriptions
    # pinned to a version keep their entitlement snapshot forever.
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_plan_versions_status",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version", name="uq_plan_versions_plan_version"),
    )
    op.create_table(
        "plan_entitlements",
        sa.Column("plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=30), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("limit_value >= 0", name="ck_plan_entitlements_limit"),
        sa.CheckConstraint(_USAGE_METRIC_CHECK, name="ck_plan_entitlements_metric"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"]),
        sa.PrimaryKeyConstraint("plan_version_id", "metric"),
    )
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('trialing', 'active', 'expired', 'cancelled')",
            name="ck_tenant_subscriptions_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])
    # Append-only usage ledger: reservations settle through confirm/release
    # entries keyed by reservation_id, and idempotent retries reuse the caller's
    # idempotency key instead of double-counting.
    op.create_table(
        "usage_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_USAGE_METRIC_CHECK, name="ck_usage_ledger_entries_metric"),
        sa.CheckConstraint("amount > 0", name="ck_usage_ledger_entries_amount"),
        sa.CheckConstraint(
            "entry_type IN ('reserve', 'confirm', 'release')",
            name="ck_usage_ledger_entries_entry_type",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_usage_ledger_tenant_idempotency",
        ),
        sa.UniqueConstraint(
            "reservation_id",
            "entry_type",
            name="uq_usage_ledger_reservation_type",
        ),
    )
    op.create_index("ix_usage_ledger_entries_tenant_id", "usage_ledger_entries", ["tenant_id"])
    op.create_index(
        "ix_usage_ledger_entries_tenant_metric",
        "usage_ledger_entries",
        ["tenant_id", "metric"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tenant_subscriptions_current ON tenant_subscriptions (tenant_id) "
        "WHERE status IN ('trialing', 'active')"
    )

    # Platform administrators (the reservation sweeper) read and write across
    # tenants through the app.platform_admin GUC.
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
            f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
        )

    # Migration 0003 set default privileges granting full CRUD to the app role
    # on every new table; revoke the excess so each table keeps only the
    # privileges its access pattern needs.
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE plans FROM {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE plan_entitlements FROM {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE plan_versions FROM {_APP_ROLE}")
    op.execute(f"REVOKE DELETE ON TABLE tenant_subscriptions FROM {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE usage_ledger_entries FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE plans TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE plan_entitlements TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE plan_versions TO {_APP_ROLE}")
    op.execute(f"GRANT UPDATE (status) ON TABLE plan_versions TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE tenant_subscriptions TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE usage_ledger_entries TO {_APP_ROLE}")

    plans = sa.table(
        "plans",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        plans,
        [{"id": _TRIAL_PLAN_ID, "code": "trial", "name": "试用套餐", "is_active": True}],
    )
    plan_versions = sa.table(
        "plan_versions",
        sa.column("id", sa.Uuid),
        sa.column("plan_id", sa.Uuid),
        sa.column("version", sa.Integer),
        sa.column("status", sa.String),
    )
    op.bulk_insert(
        plan_versions,
        [
            {
                "id": _TRIAL_PLAN_VERSION_ID,
                "plan_id": _TRIAL_PLAN_ID,
                "version": 1,
                "status": "published",
            }
        ],
    )
    plan_entitlements = sa.table(
        "plan_entitlements",
        sa.column("plan_version_id", sa.Uuid),
        sa.column("metric", sa.String),
        sa.column("limit_value", sa.Integer),
    )
    op.bulk_insert(
        plan_entitlements,
        [
            {
                "plan_version_id": _TRIAL_PLAN_VERSION_ID,
                "metric": metric,
                "limit_value": limit_value,
            }
            for metric, limit_value in _TRIAL_ENTITLEMENTS
        ],
    )


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX uq_tenant_subscriptions_current")
    op.drop_index(
        "ix_usage_ledger_entries_tenant_metric",
        table_name="usage_ledger_entries",
    )
    op.drop_index("ix_usage_ledger_entries_tenant_id", table_name="usage_ledger_entries")
    op.drop_table("usage_ledger_entries")
    op.drop_index("ix_tenant_subscriptions_tenant_id", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_table("plan_versions")
    op.drop_table("plans")
