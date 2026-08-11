"""LLM call audit, encrypted raw responses, and diagnostics.

Revision ID: 0011_llm_call_audit
Revises: 0010_online_llm_configuration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_llm_call_audit"
down_revision: str | None = "0010_online_llm_configuration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_PLATFORM_WORKER_ROLE = "relationship_platform_worker"
_MAINTENANCE_ROLE = "relationship_llm_maintenance"
_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"
_SCOPE_KEY_EXPRESSION = "CASE WHEN scope = 'platform' THEN 'platform' ELSE tenant_id::text END"


def _create_role(role: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN; "
        "END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT {role} TO CURRENT_USER")


def _drop_old_call_invariants() -> None:
    op.execute("DROP TRIGGER trg_llm_call_records_immutable ON llm_call_records")
    op.execute("DROP TRIGGER trg_llm_call_outcome_events_immutable ON llm_call_outcome_events")


def _expand_call_records() -> None:
    op.drop_constraint("ck_llm_call_records_type", "llm_call_records", type_="check")
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.alter_column("llm_call_records", "platform_attempt_id", nullable=True)
    op.add_column(
        "llm_call_records",
        sa.Column(
            "scope_key",
            sa.String(length=50),
            sa.Computed(_SCOPE_KEY_EXPRESSION, persisted=True),
            nullable=False,
        ),
    )
    op.add_column(
        "llm_call_records",
        sa.Column("job_requirement_parsing_task_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "llm_call_records",
        sa.Column("configuration_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column("llm_call_records", sa.Column("input_snapshot_id", sa.Uuid(), nullable=True))
    op.add_column("llm_call_records", sa.Column("correlation_call_id", sa.Uuid(), nullable=True))
    op.add_column(
        "llm_call_records", sa.Column("prompt_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "llm_call_records",
        sa.Column("requirement_schema_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "llm_call_records",
        sa.Column(
            "input_sources_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "llm_call_records", sa.Column("input_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column("llm_call_records", sa.Column("input_length", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE llm_call_records calls SET "
        "prompt_sha256 = prompts.sha256, "
        "requirement_schema_sha256 = schemas.sha256, "
        "input_sources_summary = jsonb_build_object('kind', 'fixed_platform_probe'), "
        "input_sha256 = calls.request_hash, input_length = 0 "
        "FROM prompt_versions prompts, job_requirement_schema_versions schemas "
        "WHERE prompts.id = calls.prompt_version_id "
        "AND schemas.id = calls.requirement_schema_version_id"
    )
    for column in (
        "prompt_sha256",
        "requirement_schema_sha256",
        "input_sources_summary",
        "input_sha256",
        "input_length",
    ):
        op.alter_column("llm_call_records", column, nullable=False)
    op.create_foreign_key(
        "fk_llm_call_records_configuration_version",
        "llm_call_records",
        "llm_configuration_versions",
        ["configuration_version_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_llm_call_records_type",
        "llm_call_records",
        "call_type IN ('config_probe', 'job_requirement_parsing')",
    )
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        "(scope = 'platform' AND tenant_id IS NULL "
        "AND call_type = 'config_probe' AND platform_attempt_id IS NOT NULL "
        "AND job_requirement_parsing_task_id IS NULL) OR "
        "(scope = 'tenant' AND tenant_id IS NOT NULL "
        "AND call_type = 'job_requirement_parsing' AND platform_attempt_id IS NULL "
        "AND job_requirement_parsing_task_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_llm_call_records_request_number", "llm_call_records", "request_number > 0"
    )
    op.create_check_constraint(
        "ck_llm_call_records_input_length", "llm_call_records", "input_length >= 0"
    )
    op.create_unique_constraint(
        "uq_llm_call_records_id_scope_key", "llm_call_records", ["id", "scope_key"]
    )
    op.create_index(
        "uq_llm_call_records_tenant_task_request",
        "llm_call_records",
        ["tenant_id", "job_requirement_parsing_task_id", "request_number"],
        unique=True,
        postgresql_where=sa.text("scope = 'tenant'"),
    )
    op.create_index(
        "ix_llm_call_records_created_id",
        "llm_call_records",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )


def _expand_outcomes() -> None:
    op.drop_constraint(
        "llm_call_outcome_events_call_id_fkey", "llm_call_outcome_events", type_="foreignkey"
    )
    op.add_column(
        "llm_call_outcome_events", sa.Column("scope", sa.String(length=20), nullable=True)
    )
    op.add_column("llm_call_outcome_events", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.add_column(
        "llm_call_outcome_events",
        sa.Column(
            "scope_key",
            sa.String(length=50),
            sa.Computed(_SCOPE_KEY_EXPRESSION, persisted=True),
            nullable=True,
        ),
    )
    op.add_column("llm_call_outcome_events", sa.Column("http_status", sa.Integer(), nullable=True))
    op.add_column("llm_call_outcome_events", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE llm_call_outcome_events outcomes SET scope = calls.scope, "
        "tenant_id = calls.tenant_id FROM llm_call_records calls "
        "WHERE calls.id = outcomes.call_id"
    )
    op.alter_column("llm_call_outcome_events", "scope", nullable=False)
    op.alter_column("llm_call_outcome_events", "scope_key", nullable=False)
    op.create_check_constraint(
        "ck_llm_call_outcomes_scope",
        "llm_call_outcome_events",
        "(scope = 'platform' AND tenant_id IS NULL) OR "
        "(scope = 'tenant' AND tenant_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_llm_call_outcomes_duration",
        "llm_call_outcome_events",
        "duration_ms IS NULL OR duration_ms >= 0",
    )
    op.create_foreign_key(
        "fk_llm_call_outcomes_call_scope",
        "llm_call_outcome_events",
        "llm_call_records",
        ["call_id", "scope_key"],
        ["id", "scope_key"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_llm_call_outcomes_scope_call",
        "llm_call_outcome_events",
        ["scope_key", "call_id"],
    )


def _create_metadata_and_raw_tables() -> None:
    op.create_table(
        "llm_call_metadata_events",
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope_key",
            sa.String(length=50),
            sa.Computed(_SCOPE_KEY_EXPRESSION, persisted=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("generation_id", sa.String(length=200), nullable=True),
        sa.Column("actual_model", sa.String(length=200), nullable=True),
        sa.Column("actual_provider", sa.String(length=200), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(precision=18, scale=9), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.String(length=100), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence_number > 0", name="ck_llm_call_metadata_sequence"),
        sa.CheckConstraint(
            "status IN ('available', 'retry_scheduled', 'unavailable')",
            name="ck_llm_call_metadata_status",
        ),
        sa.CheckConstraint(
            "(scope = 'platform' AND tenant_id IS NULL) OR "
            "(scope = 'tenant' AND tenant_id IS NOT NULL)",
            name="ck_llm_call_metadata_scope",
        ),
        sa.CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0",
            name="ck_llm_call_metadata_prompt_tokens",
        ),
        sa.CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="ck_llm_call_metadata_completion_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_llm_call_metadata_total_tokens",
        ),
        sa.CheckConstraint("cost IS NULL OR cost >= 0", name="ck_llm_call_metadata_cost"),
        sa.ForeignKeyConstraint(
            ["call_id", "scope_key"],
            ["llm_call_records.id", "llm_call_records.scope_key"],
            name="fk_llm_call_metadata_call_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("call_id", "sequence_number"),
    )
    op.create_index(
        "ix_llm_call_metadata_scope_call",
        "llm_call_metadata_events",
        ["scope_key", "call_id"],
    )
    op.create_table(
        "llm_raw_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("response_sequence", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope_key",
            sa.String(length=50),
            sa.Computed(_SCOPE_KEY_EXPRESSION, persisted=True),
            nullable=False,
        ),
        sa.Column("key_id", sa.String(length=100), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("response_sequence > 0", name="ck_llm_raw_responses_sequence"),
        sa.CheckConstraint("octet_length(nonce) = 12", name="ck_llm_raw_responses_nonce"),
        sa.CheckConstraint(
            "(scope = 'platform' AND tenant_id IS NULL) OR "
            "(scope = 'tenant' AND tenant_id IS NOT NULL)",
            name="ck_llm_raw_responses_scope",
        ),
        sa.ForeignKeyConstraint(
            ["call_id", "scope_key"],
            ["llm_call_records.id", "llm_call_records.scope_key"],
            name="fk_llm_raw_responses_call_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_id", "response_sequence", name="uq_llm_raw_responses_call_sequence"
        ),
    )
    op.create_index(
        "ix_llm_raw_responses_scope_call", "llm_raw_responses", ["scope_key", "call_id"]
    )
    op.create_index("ix_llm_raw_responses_expires_at", "llm_raw_responses", ["expires_at"])


def _create_append_only_invariants() -> None:
    for table in (
        "llm_call_records",
        "llm_call_outcome_events",
        "llm_call_metadata_events",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
        )
    op.execute(
        "CREATE TRIGGER trg_llm_raw_responses_immutable BEFORE UPDATE ON llm_raw_responses "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )
    op.execute(
        "CREATE FUNCTION validate_llm_call_metadata_event() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ DECLARE expected_sequence integer; previous_status text; BEGIN "
        "PERFORM pg_advisory_xact_lock(hashtextextended(NEW.call_id::text, 1)); "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO expected_sequence "
        "FROM llm_call_metadata_events WHERE call_id = NEW.call_id; "
        "IF NEW.sequence_number <> expected_sequence THEN "
        "RAISE EXCEPTION 'LLM metadata sequence must be %', expected_sequence; END IF; "
        "IF expected_sequence > 1 THEN SELECT status INTO previous_status "
        "FROM llm_call_metadata_events WHERE call_id = NEW.call_id "
        "ORDER BY sequence_number DESC LIMIT 1; "
        "IF previous_status IN ('available', 'unavailable') THEN "
        "RAISE EXCEPTION 'terminal LLM metadata status cannot be extended'; END IF; END IF; "
        "IF NEW.status = 'retry_scheduled' AND NEW.next_retry_at IS NULL THEN "
        "RAISE EXCEPTION 'retry_scheduled metadata requires next_retry_at'; END IF; "
        "IF NEW.status <> 'retry_scheduled' AND NEW.next_retry_at IS NOT NULL THEN "
        "RAISE EXCEPTION 'terminal metadata cannot schedule retry'; END IF; "
        "RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_llm_call_metadata_sequence "
        "BEFORE INSERT ON llm_call_metadata_events FOR EACH ROW "
        "EXECUTE FUNCTION validate_llm_call_metadata_event()"
    )


def _create_rls() -> None:
    tables = (
        "llm_call_records",
        "llm_call_outcome_events",
        "llm_call_metadata_events",
        "llm_raw_responses",
    )
    app_scope = f"((scope = 'tenant' AND {_TENANT_MATCH}) OR {_PLATFORM_ADMIN_MATCH})"
    for table in tables[:-1]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_app_scope ON {table} TO {_APP_ROLE} "
            f"USING ({app_scope}) WITH CHECK ({app_scope})"
        )
        op.execute(
            f"CREATE POLICY {table}_platform_worker_scope ON {table} "
            f"TO {_PLATFORM_WORKER_ROLE} USING (scope = 'platform') "
            "WITH CHECK (scope = 'platform')"
        )
    op.execute("ALTER TABLE llm_raw_responses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE llm_raw_responses FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY llm_raw_responses_app_select ON llm_raw_responses "
        f"FOR SELECT TO {_APP_ROLE} USING ({_PLATFORM_ADMIN_MATCH})"
    )
    op.execute(
        "CREATE POLICY llm_raw_responses_app_insert ON llm_raw_responses "
        f"FOR INSERT TO {_APP_ROLE} WITH CHECK ((scope = 'tenant' AND {_TENANT_MATCH}) "
        f"OR {_PLATFORM_ADMIN_MATCH})"
    )
    op.execute(
        "CREATE POLICY llm_raw_responses_platform_worker_scope ON llm_raw_responses "
        f"TO {_PLATFORM_WORKER_ROLE} USING (scope = 'platform') "
        "WITH CHECK (scope = 'platform')"
    )


def _create_cleanup_function() -> None:
    op.execute(
        "CREATE FUNCTION cleanup_expired_llm_raw_responses(batch_size integer) RETURNS integer "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN "
        "WITH expired AS (SELECT id FROM llm_raw_responses "
        "WHERE expires_at <= now() ORDER BY expires_at "
        "FOR UPDATE SKIP LOCKED LIMIT GREATEST(1, LEAST(batch_size, 10000))) "
        "DELETE FROM llm_raw_responses raw USING expired WHERE raw.id = expired.id; "
        "GET DIAGNOSTICS changed = ROW_COUNT; RETURN changed; END $$"
    )
    op.execute("REVOKE ALL ON FUNCTION cleanup_expired_llm_raw_responses(integer) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION cleanup_expired_llm_raw_responses(integer) "
        f"TO {_MAINTENANCE_ROLE}"
    )


def _apply_grants() -> None:
    core_tables = "llm_call_records, llm_call_outcome_events, llm_call_metadata_events"
    op.execute(f"REVOKE ALL ON TABLE {core_tables}, llm_raw_responses FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {core_tables}, llm_raw_responses TO {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {core_tables}, llm_raw_responses FROM {_PLATFORM_WORKER_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT ON TABLE {core_tables}, llm_raw_responses TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(f"REVOKE ALL ON TABLE {core_tables}, llm_raw_responses FROM {_MAINTENANCE_ROLE}")


def upgrade() -> None:
    _create_role(_MAINTENANCE_ROLE)
    _drop_old_call_invariants()
    _expand_call_records()
    _expand_outcomes()
    _create_metadata_and_raw_tables()
    _create_append_only_invariants()
    _create_rls()
    _create_cleanup_function()
    _apply_grants()


def _drop_rls() -> None:
    for table in (
        "llm_call_records",
        "llm_call_outcome_events",
        "llm_call_metadata_events",
    ):
        op.execute(f"DROP POLICY {table}_app_scope ON {table}")
        op.execute(f"DROP POLICY {table}_platform_worker_scope ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY llm_raw_responses_app_select ON llm_raw_responses")
    op.execute("DROP POLICY llm_raw_responses_app_insert ON llm_raw_responses")
    op.execute("DROP POLICY llm_raw_responses_platform_worker_scope ON llm_raw_responses")
    op.execute("ALTER TABLE llm_raw_responses DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION cleanup_expired_llm_raw_responses(integer) FROM PUBLIC")
    op.execute(
        "REVOKE ALL ON FUNCTION cleanup_expired_llm_raw_responses(integer) "
        f"FROM {_MAINTENANCE_ROLE}"
    )
    op.execute("DROP FUNCTION cleanup_expired_llm_raw_responses(integer)")
    _drop_rls()
    op.execute("DROP TRIGGER trg_llm_call_metadata_sequence ON llm_call_metadata_events")
    op.execute("DROP FUNCTION validate_llm_call_metadata_event()")
    op.execute("DROP TRIGGER trg_llm_raw_responses_immutable ON llm_raw_responses")
    op.execute("DROP TRIGGER trg_llm_call_metadata_events_immutable ON llm_call_metadata_events")
    op.drop_table("llm_raw_responses")
    op.drop_table("llm_call_metadata_events")

    op.execute("DROP TRIGGER trg_llm_call_outcome_events_immutable ON llm_call_outcome_events")
    op.drop_index("ix_llm_call_outcomes_scope_call", table_name="llm_call_outcome_events")
    op.drop_constraint(
        "fk_llm_call_outcomes_call_scope", "llm_call_outcome_events", type_="foreignkey"
    )
    op.drop_constraint("ck_llm_call_outcomes_duration", "llm_call_outcome_events", type_="check")
    op.drop_constraint("ck_llm_call_outcomes_scope", "llm_call_outcome_events", type_="check")
    for column in ("duration_ms", "http_status", "scope_key", "tenant_id", "scope"):
        op.drop_column("llm_call_outcome_events", column)
    op.create_foreign_key(
        "llm_call_outcome_events_call_id_fkey",
        "llm_call_outcome_events",
        "llm_call_records",
        ["call_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        "CREATE TRIGGER trg_llm_call_outcome_events_immutable "
        "BEFORE UPDATE OR DELETE ON llm_call_outcome_events "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )

    op.execute("DROP TRIGGER trg_llm_call_records_immutable ON llm_call_records")
    op.drop_index("ix_llm_call_records_created_id", table_name="llm_call_records")
    op.drop_index("uq_llm_call_records_tenant_task_request", table_name="llm_call_records")
    op.drop_constraint("uq_llm_call_records_id_scope_key", "llm_call_records", type_="unique")
    op.drop_constraint("ck_llm_call_records_input_length", "llm_call_records", type_="check")
    op.drop_constraint("ck_llm_call_records_request_number", "llm_call_records", type_="check")
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.drop_constraint("ck_llm_call_records_type", "llm_call_records", type_="check")
    op.drop_constraint(
        "fk_llm_call_records_configuration_version", "llm_call_records", type_="foreignkey"
    )
    for column in (
        "input_length",
        "input_sha256",
        "input_sources_summary",
        "requirement_schema_sha256",
        "prompt_sha256",
        "correlation_call_id",
        "input_snapshot_id",
        "configuration_version_id",
        "job_requirement_parsing_task_id",
        "scope_key",
    ):
        op.drop_column("llm_call_records", column)
    op.alter_column("llm_call_records", "platform_attempt_id", nullable=False)
    op.create_check_constraint(
        "ck_llm_call_records_type", "llm_call_records", "call_type IN ('config_probe')"
    )
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        "scope = 'platform' AND tenant_id IS NULL AND platform_attempt_id IS NOT NULL",
    )
    op.execute(
        "CREATE TRIGGER trg_llm_call_records_immutable BEFORE UPDATE OR DELETE "
        "ON llm_call_records FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )

    op.execute(f"REVOKE ALL ON TABLE llm_call_records, llm_call_outcome_events FROM {_APP_ROLE}")
    op.execute(
        "GRANT SELECT, INSERT ON TABLE llm_call_records, llm_call_outcome_events "
        f"TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_MAINTENANCE_ROLE}")
    op.execute(f"REVOKE {_MAINTENANCE_ROLE} FROM CURRENT_USER")
    op.execute(f"DROP ROLE IF EXISTS {_MAINTENANCE_ROLE}")
