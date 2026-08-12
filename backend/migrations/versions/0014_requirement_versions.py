"""Immutable job requirement versions, current pointer, and legacy activation gate.

Revision ID: 0014_requirement_versions
Revises: 0013_requirement_draft_editing
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0014_requirement_versions"
down_revision: str | None = "0013_requirement_draft_editing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"


def upgrade() -> None:
    _create_versions_table()
    _relax_draft_provenance()
    _add_job_version_pointer_and_legacy()
    _enable_versions_rls_and_immutability()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_jobs_reject_legacy_grant ON jobs")
    op.execute("DROP FUNCTION IF EXISTS reject_legacy_requirement_exempt_grant()")
    op.drop_constraint("ck_jobs_active_requires_requirement_version", "jobs", type_="check")
    op.drop_constraint("fk_jobs_current_requirement_version", "jobs", type_="foreignkey")
    op.drop_column("jobs", "current_requirement_version_id")
    op.drop_column("jobs", "legacy_requirement_exempt")

    op.drop_constraint(
        "fk_requirement_drafts_source_version",
        "job_requirement_drafts",
        type_="foreignkey",
    )
    op.drop_column("job_requirement_drafts", "source_version_id")
    op.drop_index("uq_requirement_drafts_task", table_name="job_requirement_drafts")
    op.create_unique_constraint(
        "uq_requirement_drafts_task",
        "job_requirement_drafts",
        ["task_id"],
    )
    op.alter_column(
        "job_requirement_drafts",
        "input_snapshot_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "job_requirement_drafts",
        "task_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_job_requirement_versions_immutable ON job_requirement_versions"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON job_requirement_versions")
    op.execute(f"REVOKE ALL ON TABLE job_requirement_versions FROM {_APP_ROLE}")
    op.drop_table("job_requirement_versions")


def _create_versions_table() -> None:
    op.create_table(
        "job_requirement_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("requirement_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("input_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version_number > 0", name="ck_requirement_versions_number"),
        sa.ForeignKeyConstraint(
            ["job_id", "tenant_id"],
            ["jobs.id", "jobs.tenant_id"],
            name="fk_requirement_versions_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "tenant_id", "job_id"],
            [
                "job_requirement_drafts.id",
                "job_requirement_drafts.tenant_id",
                "job_requirement_drafts.job_id",
            ],
            name="fk_requirement_versions_draft_tenant_job",
        ),
        sa.ForeignKeyConstraint(
            ["input_snapshot_id", "tenant_id"],
            [
                "job_requirement_input_snapshots.id",
                "job_requirement_input_snapshots.tenant_id",
            ],
            name="fk_requirement_versions_snapshot_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_schema_version_id"],
            ["job_requirement_schema_versions.id"],
            name="fk_requirement_versions_schema",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name="fk_requirement_versions_confirmed_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "job_id",
            "version_number",
            name="uq_requirement_versions_tenant_job_number",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "job_id",
            name="uq_requirement_versions_id_tenant_job",
        ),
        sa.UniqueConstraint("draft_id", name="uq_requirement_versions_draft"),
    )
    op.create_foreign_key(
        "fk_requirement_versions_source_version",
        "job_requirement_versions",
        "job_requirement_versions",
        ["source_version_id", "tenant_id", "job_id"],
        ["id", "tenant_id", "job_id"],
    )
    op.create_index(
        "ix_requirement_versions_tenant_job",
        "job_requirement_versions",
        ["tenant_id", "job_id"],
    )


def _relax_draft_provenance() -> None:
    op.drop_constraint("uq_requirement_drafts_task", "job_requirement_drafts", type_="unique")
    op.alter_column(
        "job_requirement_drafts",
        "task_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "job_requirement_drafts",
        "input_snapshot_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_index(
        "uq_requirement_drafts_task",
        "job_requirement_drafts",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("task_id IS NOT NULL"),
    )
    op.add_column(
        "job_requirement_drafts",
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_requirement_drafts_source_version",
        "job_requirement_drafts",
        "job_requirement_versions",
        ["source_version_id", "tenant_id", "job_id"],
        ["id", "tenant_id", "job_id"],
    )


def _add_job_version_pointer_and_legacy() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "legacy_requirement_exempt",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("current_requirement_version_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        "UPDATE jobs SET legacy_requirement_exempt = true "
        "WHERE status = 'active' AND current_requirement_version_id IS NULL"
    )
    op.create_foreign_key(
        "fk_jobs_current_requirement_version",
        "jobs",
        "job_requirement_versions",
        ["current_requirement_version_id", "tenant_id", "id"],
        ["id", "tenant_id", "job_id"],
    )
    op.create_check_constraint(
        "ck_jobs_active_requires_requirement_version",
        "jobs",
        "status <> 'active' OR current_requirement_version_id IS NOT NULL "
        "OR legacy_requirement_exempt",
    )
    op.execute(
        "CREATE FUNCTION reject_legacy_requirement_exempt_grant() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF NEW.legacy_requirement_exempt = true "
        "AND OLD.legacy_requirement_exempt = false THEN "
        "RAISE EXCEPTION 'legacy_requirement_exempt cannot be granted by application'; "
        "END IF; RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_jobs_reject_legacy_grant BEFORE UPDATE ON jobs "
        "FOR EACH ROW EXECUTE FUNCTION reject_legacy_requirement_exempt_grant()"
    )


def _enable_versions_rls_and_immutability() -> None:
    op.execute(
        "CREATE TRIGGER trg_job_requirement_versions_immutable "
        "BEFORE UPDATE OR DELETE ON job_requirement_versions "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )
    op.execute("ALTER TABLE job_requirement_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_requirement_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON job_requirement_versions TO "
        f"{_APP_ROLE} USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
    )
    op.execute(f"REVOKE ALL ON TABLE job_requirement_versions FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE job_requirement_versions TO {_APP_ROLE}")
