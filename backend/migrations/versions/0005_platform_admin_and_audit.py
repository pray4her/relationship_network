from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_platform_admin_and_audit"
down_revision: str | None = "0004_invitations_and_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_USER_MATCH = "user_id = nullif(current_setting('app.user_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "tenants",
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.create_check_constraint(
        "ck_tenants_status",
        "tenants",
        "status IN ('active', 'suspended')",
    )

    # Platform administrators read across tenants through the app.platform_admin
    # GUC; membership writes stay pinned to the tenant/user context.
    op.execute("DROP POLICY tenant_isolation ON tenant_memberships")
    op.execute(
        "CREATE POLICY tenant_isolation ON tenant_memberships "
        f"USING ({_TENANT_MATCH} OR {_USER_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_USER_MATCH})"
    )

    # Append-only audit trail for platform administration. The table is
    # platform-wide (no tenant RLS); the app role may insert and read but
    # never update or delete, and rows are only exposed through admin routes.
    # actor_id survives user deletion so the trail outlives its actors.
    op.create_table(
        "platform_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=1000), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_audit_events_actor_id",
        "platform_audit_events",
        ["actor_id"],
    )
    op.create_index(
        "ix_platform_audit_events_action",
        "platform_audit_events",
        ["action"],
    )
    op.execute(f"GRANT SELECT, INSERT ON TABLE platform_audit_events TO {_APP_ROLE}")


def downgrade() -> None:
    op.drop_index("ix_platform_audit_events_action", table_name="platform_audit_events")
    op.drop_index("ix_platform_audit_events_actor_id", table_name="platform_audit_events")
    op.drop_table("platform_audit_events")
    op.execute("DROP POLICY tenant_isolation ON tenant_memberships")
    op.execute(
        "CREATE POLICY tenant_isolation ON tenant_memberships "
        f"USING ({_TENANT_MATCH} OR {_USER_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_USER_MATCH})"
    )
    op.drop_constraint("ck_tenants_status", "tenants", type_="check")
    op.drop_column("tenants", "status")
    op.drop_column("users", "is_platform_admin")
