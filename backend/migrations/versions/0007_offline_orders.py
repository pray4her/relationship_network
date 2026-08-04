import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision: str = "0007_offline_orders"
down_revision: str | None = "0006_billing_and_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"

# Deterministic seed identifiers (uuid5) keep upgrade/downgrade cycles repeatable.
_STANDARD_PLAN_ID = uuid.uuid5(uuid.NAMESPACE_URL, "relationship-network/billing/standard/plan")
_STANDARD_PLAN_VERSION_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "relationship-network/billing/standard/plan-version"
)
_STANDARD_ENTITLEMENTS = (
    ("owners", 3),
    ("companies", 5),
    ("active_jobs", 20),
    ("searches", 500),
    ("matches", 50),
    ("reports", 20),
)


def upgrade() -> None:
    # Offline orders move through pending -> confirmed/rejected under platform
    # administrator review, so the table is not append-only: the app role
    # keeps UPDATE but not DELETE.
    op.create_table(
        "offline_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("payment_reference", sa.Text(), nullable=False),
        sa.Column(
            "payment_channel",
            sa.String(length=20),
            server_default="offline",
            nullable=False,
        ),
        sa.Column("payer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_offline_orders_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_offline_orders_tenant_idempotency",
        ),
    )
    op.create_index("ix_offline_orders_tenant_id", "offline_orders", ["tenant_id"])

    op.execute("ALTER TABLE offline_orders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE offline_orders FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON offline_orders "
        f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
    )

    # Migration 0003 set default privileges granting full CRUD to the app role
    # on every new table; revoke the excess so the table keeps only the
    # privileges its access pattern needs.
    op.execute(f"REVOKE DELETE ON TABLE offline_orders FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE offline_orders TO {_APP_ROLE}")

    op.add_column(
        "tenant_subscriptions",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("offline_order_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tenant_subscriptions_offline_order_id",
        "tenant_subscriptions",
        "offline_orders",
        ["offline_order_id"],
        ["id"],
    )

    plans = sa.table(
        "plans",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.execute(
        pg_insert(plans)
        .values(
            [{"id": _STANDARD_PLAN_ID, "code": "standard", "name": "标准版", "is_active": True}]
        )
        .on_conflict_do_nothing()
    )
    plan_versions = sa.table(
        "plan_versions",
        sa.column("id", sa.Uuid),
        sa.column("plan_id", sa.Uuid),
        sa.column("version", sa.Integer),
        sa.column("status", sa.String),
    )
    op.execute(
        pg_insert(plan_versions)
        .values(
            [
                {
                    "id": _STANDARD_PLAN_VERSION_ID,
                    "plan_id": _STANDARD_PLAN_ID,
                    "version": 1,
                    "status": "published",
                }
            ]
        )
        .on_conflict_do_nothing()
    )
    plan_entitlements = sa.table(
        "plan_entitlements",
        sa.column("plan_version_id", sa.Uuid),
        sa.column("metric", sa.String),
        sa.column("limit_value", sa.Integer),
    )
    op.execute(
        pg_insert(plan_entitlements)
        .values(
            [
                {
                    "plan_version_id": _STANDARD_PLAN_VERSION_ID,
                    "metric": metric,
                    "limit_value": limit_value,
                }
                for metric, limit_value in _STANDARD_ENTITLEMENTS
            ]
        )
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM plan_entitlements WHERE plan_version_id = :version_id").bindparams(
            sa.bindparam("version_id", value=_STANDARD_PLAN_VERSION_ID, type_=sa.Uuid)
        )
    )
    op.execute(
        sa.text("DELETE FROM plan_versions WHERE id = :version_id").bindparams(
            sa.bindparam("version_id", value=_STANDARD_PLAN_VERSION_ID, type_=sa.Uuid)
        )
    )
    op.execute(
        sa.text("DELETE FROM plans WHERE id = :plan_id").bindparams(
            sa.bindparam("plan_id", value=_STANDARD_PLAN_ID, type_=sa.Uuid)
        )
    )
    op.drop_constraint(
        "fk_tenant_subscriptions_offline_order_id",
        "tenant_subscriptions",
        type_="foreignkey",
    )
    op.drop_column("tenant_subscriptions", "offline_order_id")
    op.drop_column("tenant_subscriptions", "cancel_requested_at")
    op.execute("DROP POLICY tenant_isolation ON offline_orders")
    op.execute("ALTER TABLE offline_orders DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_offline_orders_tenant_id", table_name="offline_orders")
    op.drop_table("offline_orders")
