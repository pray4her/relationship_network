from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_rbac_and_rls"
down_revision: str | None = "0002_auth_and_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_USER_MATCH = "user_id = nullif(current_setting('app.user_id', true), '')::uuid"

_TENANT_TABLES = ("roles", "role_permissions", "membership_roles")

_APP_ROLE = "relationship_app"
_GRANT_TABLES = "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public"


def upgrade() -> None:
    # Dedicated non-superuser role for application traffic; without it the
    # owning superuser would bypass row level security entirely.
    op.execute(
        f"DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN "
        f"CREATE ROLE {_APP_ROLE} NOLOGIN; "
        f"END IF; "
        f"END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
    op.execute(f"{_GRANT_TABLES} TO {_APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_APP_ROLE}"
    )
    op.execute(f"GRANT {_APP_ROLE} TO CURRENT_USER")

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=200), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_table(
        "role_permissions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission"),
    )
    op.create_index("ix_role_permissions_tenant_id", "role_permissions", ["tenant_id"])
    op.create_table(
        "membership_roles",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["tenant_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("membership_id", "role_id"),
    )
    op.create_index("ix_membership_roles_tenant_id", "membership_roles", ["tenant_id"])

    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_TENANT_MATCH}) "
            f"WITH CHECK ({_TENANT_MATCH})"
        )
    op.execute("ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON tenant_memberships "
        f"USING ({_TENANT_MATCH} OR {_USER_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_USER_MATCH})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY tenant_isolation ON tenant_memberships")
    op.execute("ALTER TABLE tenant_memberships DISABLE ROW LEVEL SECURITY")
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
    op.drop_index("ix_membership_roles_tenant_id", table_name="membership_roles")
    op.drop_table("membership_roles")
    op.drop_index("ix_role_permissions_tenant_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_table("roles")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {_APP_ROLE}"
    )
    op.execute(f"REVOKE {_APP_ROLE} FROM CURRENT_USER")
    op.execute(f"REVOKE ALL ON SCHEMA public FROM {_APP_ROLE}")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {_APP_ROLE}"
    )
    op.execute(f"DROP ROLE {_APP_ROLE}")
