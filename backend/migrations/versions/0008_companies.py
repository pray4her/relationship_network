"""Companies, documents, tenant audit, and vacate ledger entries.

Revision ID: 0008_companies
Revises: 0007_offline_orders
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_companies"
down_revision: str | None = "0007_offline_orders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"


def _enable_tenant_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
    )


def upgrade() -> None:
    op.drop_constraint(
        "ck_usage_ledger_entries_entry_type",
        "usage_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_usage_ledger_entries_entry_type",
        "usage_ledger_entries",
        "entry_type IN ('reserve', 'confirm', 'release', 'vacate')",
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("profile_text", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("usage_reservation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_companies_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"])
    op.create_index("ix_companies_tenant_status", "companies", ["tenant_id", "status"])
    _enable_tenant_rls("companies")
    op.execute(f"REVOKE DELETE ON TABLE companies FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE companies TO {_APP_ROLE}")

    op.create_table(
        "company_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "scan_status",
            sa.String(length=30),
            server_default="content_checked",
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_company_documents_byte_size"),
        sa.CheckConstraint(
            "scan_status IN ('clean', 'rejected', 'content_checked')",
            name="ck_company_documents_scan_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_company_documents_storage_key"),
    )
    op.create_index("ix_company_documents_tenant_id", "company_documents", ["tenant_id"])
    op.create_index("ix_company_documents_company_id", "company_documents", ["company_id"])
    _enable_tenant_rls("company_documents")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE company_documents FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE company_documents TO {_APP_ROLE}")

    op.create_table(
        "tenant_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_audit_events_tenant_id", "tenant_audit_events", ["tenant_id"])
    op.create_index(
        "ix_tenant_audit_events_target",
        "tenant_audit_events",
        ["tenant_id", "target_type", "target_id"],
    )
    _enable_tenant_rls("tenant_audit_events")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE tenant_audit_events FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE tenant_audit_events TO {_APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_audit_events")
    op.drop_table("tenant_audit_events")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON company_documents")
    op.drop_table("company_documents")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON companies")
    op.drop_table("companies")

    op.drop_constraint(
        "ck_usage_ledger_entries_entry_type",
        "usage_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_usage_ledger_entries_entry_type",
        "usage_ledger_entries",
        "entry_type IN ('reserve', 'confirm', 'release')",
    )
