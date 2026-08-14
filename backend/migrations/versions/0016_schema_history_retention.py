"""Schema upgrade records, input body retention purge, and maintenance path.

Revision ID: 0016_schema_history_retention
Revises: 0015_repair_requirement_tasks
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_schema_history_retention"
down_revision: str | None = "0015_repair_requirement_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_MAINTENANCE_ROLE = "relationship_requirement_maintenance"
_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"
_UPGRADES_TABLE = "job_requirement_draft_schema_upgrades"
_SOURCES_TABLE = "job_requirement_input_sources"
_CLEANUP_FUNCTION = "cleanup_expired_requirement_input_bodies"
_RETENTION = "90 days"


def _create_role(role: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN; "
        "END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT {role} TO CURRENT_USER")


def _prepare_source_body_purge() -> None:
    for column in ("original_text", "corrected_text", "sent_text"):
        op.alter_column(_SOURCES_TABLE, column, nullable=True)
    op.add_column(
        _SOURCES_TABLE,
        sa.Column("body_purged_at", sa.DateTime(timezone=True), nullable=True),
    )


def _create_upgrades_table() -> None:
    op.create_table(
        _UPGRADES_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("from_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("to_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("converter_version", sa.String(length=100), nullable=False),
        sa.Column("pre_upgrade_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("item_mappings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "lossy_resolutions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "tenant_id", "job_id"],
            [
                "job_requirement_drafts.id",
                "job_requirement_drafts.tenant_id",
                "job_requirement_drafts.job_id",
            ],
            name="fk_requirement_schema_upgrades_draft_tenant_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "tenant_id"],
            ["jobs.id", "jobs.tenant_id"],
            name="fk_requirement_schema_upgrades_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_schema_version_id"],
            ["job_requirement_schema_versions.id"],
            name="fk_requirement_schema_upgrades_from_schema",
        ),
        sa.ForeignKeyConstraint(
            ["to_schema_version_id"],
            ["job_requirement_schema_versions.id"],
            name="fk_requirement_schema_upgrades_to_schema",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_requirement_schema_upgrades_actor",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_requirement_schema_upgrades_id_tenant"),
    )
    op.create_index(
        "ix_requirement_schema_upgrades_tenant_draft",
        _UPGRADES_TABLE,
        ["tenant_id", "draft_id"],
    )


def _enable_rls_and_grants() -> None:
    op.execute(f"ALTER TABLE {_UPGRADES_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_UPGRADES_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {_UPGRADES_TABLE} TO {_APP_ROLE} "
        f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
    )
    op.execute(f"REVOKE ALL ON TABLE {_UPGRADES_TABLE} FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {_UPGRADES_TABLE} TO {_APP_ROLE}")
    op.execute(f"GRANT UPDATE (lossy_resolutions) ON TABLE {_UPGRADES_TABLE} TO {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {_UPGRADES_TABLE} FROM {_MAINTENANCE_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {_SOURCES_TABLE} FROM {_MAINTENANCE_ROLE}")


def _create_cleanup_function() -> None:
    op.execute(
        f"CREATE FUNCTION {_CLEANUP_FUNCTION}(batch_size integer) RETURNS integer "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN "
        "WITH expired AS (SELECT src.id FROM job_requirement_input_sources src "
        "JOIN job_requirement_input_snapshots snap "
        "ON snap.id = src.snapshot_id AND snap.tenant_id = src.tenant_id "
        "WHERE src.body_purged_at IS NULL "
        f"AND snap.created_at <= now() - interval '{_RETENTION}' "
        "AND NOT EXISTS (SELECT 1 FROM job_requirement_versions versions "
        "WHERE versions.input_snapshot_id = snap.id) "
        "ORDER BY snap.created_at "
        "FOR UPDATE OF src SKIP LOCKED LIMIT GREATEST(1, LEAST(batch_size, 10000))) "
        f"UPDATE {_SOURCES_TABLE} sources SET original_text = NULL, corrected_text = NULL, "
        "sent_text = NULL, body_purged_at = now() "
        "FROM expired WHERE sources.id = expired.id; "
        "GET DIAGNOSTICS changed = ROW_COUNT; RETURN changed; END $$"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_CLEANUP_FUNCTION}(integer) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_CLEANUP_FUNCTION}(integer) TO {_MAINTENANCE_ROLE}")


def _allow_source_body_purge() -> None:
    """Replace blanket source immutability with a purge-only update invariant.

    Migration 0012 forbids every UPDATE on input sources; the retention purge
    is the single sanctioned mutation, so the trigger now rejects deletes and
    any update that is not exactly "text bodies to NULL, purge marker set".
    """
    op.execute(f"DROP TRIGGER trg_{_SOURCES_TABLE}_immutable ON {_SOURCES_TABLE}")
    op.execute(
        "CREATE FUNCTION validate_requirement_input_source_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP = 'DELETE' THEN "
        "RAISE EXCEPTION 'immutable LLM record cannot be changed'; END IF; "
        "IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.job_id <> OLD.job_id "
        "OR NEW.snapshot_id <> OLD.snapshot_id OR NEW.source_id <> OLD.source_id "
        "OR NEW.source_kind <> OLD.source_kind "
        "OR NEW.material_id IS DISTINCT FROM OLD.material_id "
        "OR NEW.position <> OLD.position OR NEW.original_sha256 <> OLD.original_sha256 "
        "OR NEW.sent_sha256 <> OLD.sent_sha256 "
        "OR NEW.unicode_characters <> OLD.unicode_characters "
        "OR NEW.edited_by IS DISTINCT FROM OLD.edited_by "
        "OR NEW.edited_at <> OLD.edited_at THEN "
        "RAISE EXCEPTION 'immutable LLM record cannot be changed'; END IF; "
        "IF OLD.body_purged_at IS NOT NULL OR NEW.body_purged_at IS NULL "
        "OR NEW.original_text IS NOT NULL OR NEW.corrected_text IS NOT NULL "
        "OR NEW.sent_text IS NOT NULL THEN "
        "RAISE EXCEPTION 'immutable LLM record cannot be changed'; END IF; "
        "RETURN NEW; END $$"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_SOURCES_TABLE}_immutable BEFORE UPDATE OR DELETE "
        f"ON {_SOURCES_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION validate_requirement_input_source_mutation()"
    )


def _restore_source_immutability() -> None:
    op.execute(f"DROP TRIGGER trg_{_SOURCES_TABLE}_immutable ON {_SOURCES_TABLE}")
    op.execute("DROP FUNCTION validate_requirement_input_source_mutation()")
    op.execute(
        f"CREATE TRIGGER trg_{_SOURCES_TABLE}_immutable BEFORE UPDATE OR DELETE "
        f"ON {_SOURCES_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )


def upgrade() -> None:
    _create_role(_MAINTENANCE_ROLE)
    _prepare_source_body_purge()
    _create_upgrades_table()
    _enable_rls_and_grants()
    _create_cleanup_function()
    _allow_source_body_purge()


def downgrade() -> None:
    _restore_source_immutability()
    op.execute(f"REVOKE ALL ON FUNCTION {_CLEANUP_FUNCTION}(integer) FROM {_MAINTENANCE_ROLE}")
    op.execute(f"REVOKE ALL ON FUNCTION {_CLEANUP_FUNCTION}(integer) FROM PUBLIC")
    op.execute(f"DROP FUNCTION {_CLEANUP_FUNCTION}(integer)")
    op.execute(f"DROP POLICY tenant_isolation ON {_UPGRADES_TABLE}")
    op.execute(f"ALTER TABLE {_UPGRADES_TABLE} DISABLE ROW LEVEL SECURITY")
    op.drop_table(_UPGRADES_TABLE)
    op.drop_column(_SOURCES_TABLE, "body_purged_at")
    op.execute(
        f"UPDATE {_SOURCES_TABLE} SET original_text = '', corrected_text = '', sent_text = '' "
        "WHERE original_text IS NULL"
    )
    for column in ("original_text", "corrected_text", "sent_text"):
        op.alter_column(_SOURCES_TABLE, column, nullable=False)
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_MAINTENANCE_ROLE}")
    op.execute(f"REVOKE {_MAINTENANCE_ROLE} FROM CURRENT_USER")
