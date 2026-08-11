"""Immutable online LLM configuration and durable platform probe execution.

Revision ID: 0010_online_llm_configuration
Revises: 0009_jobs
"""

import json
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from relationship_network_api.llm_assets import manifest

revision: str = "0010_online_llm_configuration"
down_revision: str | None = "0009_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_PLATFORM_WORKER_ROLE = "relationship_platform_worker"
_OUTBOX_DISPATCHER_ROLE = "relationship_outbox_dispatcher"
_BOOTSTRAP_VERSION_ID = UUID("00000000-0000-0000-0000-000000000110")

_ATTEMPT_STATUSES = (
    "queued",
    "running",
    "retry_scheduled",
    "cancel_requested",
    "succeeded",
    "failed",
    "conflicted",
    "cancelled",
)
_NONTERMINAL_STATUSES = ("queued", "running", "retry_scheduled", "cancel_requested")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_role(role: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN; "
        "END IF; "
        "END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT {role} TO CURRENT_USER")


def _create_tables() -> None:
    op.create_table(
        "job_requirement_schema_versions",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("schema_id", sa.String(length=200), nullable=False),
        sa.Column("asset_path", sa.String(length=300), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_catalog", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "chinese_identity_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("output_limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_path"),
        sa.UniqueConstraint("schema_id"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("compatible_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("asset_path", sa.String(length=300), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["compatible_schema_version_id"],
            ["job_requirement_schema_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_path"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_table(
        "llm_configuration_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="openrouter", nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=100), nullable=False),
        sa.Column("requirement_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("temperature", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("privacy_routing", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=30), server_default="probe", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version_number > 0", name="ck_llm_configuration_versions_number"),
        sa.CheckConstraint(
            "temperature >= 0 AND temperature <= 1",
            name="ck_llm_configuration_versions_temperature",
        ),
        sa.CheckConstraint(
            "max_output_tokens BETWEEN 1024 AND 16384",
            name="ck_llm_configuration_versions_max_output_tokens",
        ),
        sa.CheckConstraint(
            "request_timeout_seconds BETWEEN 30 AND 300",
            name="ck_llm_configuration_versions_timeout",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["requirement_schema_version_id"],
            ["job_requirement_schema_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_number"),
    )
    op.create_table(
        "llm_configuration_current",
        sa.Column("singleton", sa.Boolean(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("singleton", name="ck_llm_configuration_current_singleton"),
        sa.ForeignKeyConstraint(["version_id"], ["llm_configuration_versions.id"]),
        sa.PrimaryKeyConstraint("singleton"),
        sa.UniqueConstraint("version_id"),
    )
    op.create_table(
        "llm_configuration_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("candidate_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_current_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("external_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("structured_invalid_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
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
        sa.CheckConstraint(
            f"status IN ({_quoted(_ATTEMPT_STATUSES)})",
            name="ck_llm_configuration_attempts_status",
        ),
        sa.CheckConstraint(
            "external_call_count BETWEEN 0 AND 3",
            name="ck_llm_configuration_attempts_call_budget",
        ),
        sa.CheckConstraint(
            "structured_invalid_count BETWEEN 0 AND 2",
            name="ck_llm_configuration_attempts_invalid_budget",
        ),
        sa.ForeignKeyConstraint(
            ["expected_current_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_llm_configuration_attempts_one_nonterminal",
        "llm_configuration_attempts",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_quoted(_NONTERMINAL_STATUSES)})"),
    )
    op.create_table(
        "llm_configuration_attempt_events",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"event_type IN ({_quoted(_ATTEMPT_STATUSES)})",
            name="ck_llm_attempt_events_type",
        ),
        sa.CheckConstraint("sequence_number > 0", name="ck_llm_attempt_events_sequence"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["llm_configuration_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", "sequence_number"),
    )
    op.create_table(
        "platform_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_by", sa.Uuid(), nullable=True),
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=500), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_outbox_events_ready",
        "platform_outbox_events",
        ["available_at"],
        postgresql_where=sa.text("delivered_at IS NULL"),
    )
    op.create_index(
        "ix_platform_outbox_events_aggregate_id",
        "platform_outbox_events",
        ["aggregate_id"],
    )
    op.create_table(
        "llm_call_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=20), server_default="platform", nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("call_type", sa.String(length=30), server_default="config_probe", nullable=False),
        sa.Column("platform_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("request_number", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=100), nullable=False),
        sa.Column("requirement_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("scope IN ('platform', 'tenant')", name="ck_llm_call_records_scope"),
        sa.CheckConstraint("call_type IN ('config_probe')", name="ck_llm_call_records_type"),
        sa.CheckConstraint(
            "scope = 'platform' AND tenant_id IS NULL AND platform_attempt_id IS NOT NULL",
            name="ck_llm_call_records_scope_key",
        ),
        sa.ForeignKeyConstraint(
            ["platform_attempt_id"],
            ["llm_configuration_attempts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform_attempt_id",
            "request_number",
            name="uq_llm_call_records_attempt_request",
        ),
    )
    op.create_table(
        "llm_call_outcome_events",
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=100), server_default="", nullable=False),
        sa.Column("provider_request_id", sa.String(length=200), nullable=True),
        sa.Column("actual_model", sa.String(length=200), nullable=True),
        sa.Column("actual_provider", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence_number > 0", name="ck_llm_call_outcomes_sequence"),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'outcome_unknown', 'late_response')",
            name="ck_llm_call_outcomes_outcome",
        ),
        sa.ForeignKeyConstraint(["call_id"], ["llm_call_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("call_id", "sequence_number"),
    )


def _create_invariants() -> None:
    op.execute(
        "CREATE FUNCTION reject_immutable_llm_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'immutable LLM record cannot be changed'; "
        "END $$"
    )
    immutable_tables = (
        "job_requirement_schema_versions",
        "prompt_versions",
        "llm_configuration_versions",
        "llm_configuration_attempt_events",
        "llm_call_records",
        "llm_call_outcome_events",
    )
    for table in immutable_tables:
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
        )
    op.execute(
        "CREATE FUNCTION validate_llm_configuration_attempt_transition() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF NEW.candidate_snapshot <> OLD.candidate_snapshot "
        "OR NEW.expected_current_version_id <> OLD.expected_current_version_id "
        "OR NEW.source_version_id IS DISTINCT FROM OLD.source_version_id "
        "OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN "
        "RAISE EXCEPTION 'immutable configuration attempt fields cannot be changed'; END IF; "
        "IF OLD.status IN ('succeeded', 'failed', 'conflicted', 'cancelled') THEN "
        "RAISE EXCEPTION 'terminal configuration attempt cannot be changed'; END IF; "
        "IF NEW.status <> OLD.status AND NOT ("
        "(OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled')) OR "
        "(OLD.status = 'running' AND NEW.status IN "
        "('retry_scheduled', 'succeeded', 'failed', 'conflicted', 'cancel_requested')) OR "
        "(OLD.status = 'running' AND NEW.status = 'queued' "
        "AND OLD.lease_expires_at <= now()) OR "
        "(OLD.status = 'retry_scheduled' AND NEW.status IN ('queued', 'cancelled')) OR "
        "(OLD.status = 'cancel_requested' AND NEW.status = 'cancelled')"
        ") THEN RAISE EXCEPTION 'illegal configuration attempt transition: % -> %', "
        "OLD.status, NEW.status; END IF; "
        "IF NEW.status = 'running' AND (NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL) "
        "THEN RAISE EXCEPTION 'running attempt requires a lease'; END IF; "
        "NEW.updated_at = now(); RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_llm_configuration_attempt_transition "
        "BEFORE UPDATE ON llm_configuration_attempts FOR EACH ROW "
        "EXECUTE FUNCTION validate_llm_configuration_attempt_transition()"
    )
    op.execute(
        "CREATE FUNCTION validate_llm_configuration_attempt_event() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ DECLARE expected_sequence integer; current_status text; BEGIN "
        "SELECT status INTO current_status FROM llm_configuration_attempts "
        "WHERE id = NEW.attempt_id FOR UPDATE; "
        "IF current_status IS NULL THEN RAISE EXCEPTION 'configuration attempt not found'; END IF; "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO expected_sequence "
        "FROM llm_configuration_attempt_events WHERE attempt_id = NEW.attempt_id; "
        "IF NEW.sequence_number <> expected_sequence THEN "
        "RAISE EXCEPTION 'configuration attempt event sequence must be %', "
        "expected_sequence; END IF; "
        "IF NEW.event_type <> current_status THEN "
        "RAISE EXCEPTION 'configuration attempt event must match current status'; END IF; "
        "PERFORM pg_notify('llm_configuration_attempt_events', "
        "NEW.attempt_id::text || ':' || NEW.sequence_number::text); RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_llm_configuration_attempt_event_sequence "
        "BEFORE INSERT ON llm_configuration_attempt_events FOR EACH ROW "
        "EXECUTE FUNCTION validate_llm_configuration_attempt_event()"
    )
    op.execute(
        "CREATE FUNCTION validate_llm_call_outcome_event() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ DECLARE previous_outcome text; expected_sequence integer; BEGIN "
        "PERFORM pg_advisory_xact_lock(hashtextextended(NEW.call_id::text, 0)); "
        "IF NOT EXISTS (SELECT 1 FROM llm_call_records WHERE id = NEW.call_id) THEN "
        "RAISE EXCEPTION 'LLM call record not found'; END IF; "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO expected_sequence "
        "FROM llm_call_outcome_events WHERE call_id = NEW.call_id; "
        "IF NEW.sequence_number <> expected_sequence THEN "
        "RAISE EXCEPTION 'LLM call outcome sequence must be %', expected_sequence; END IF; "
        "IF expected_sequence = 1 AND NEW.outcome = 'late_response' THEN "
        "RAISE EXCEPTION 'late response requires an outcome_unknown event'; END IF; "
        "IF expected_sequence > 1 THEN "
        "SELECT outcome INTO previous_outcome FROM llm_call_outcome_events "
        "WHERE call_id = NEW.call_id ORDER BY sequence_number DESC LIMIT 1; "
        "IF previous_outcome <> 'outcome_unknown' OR NEW.outcome <> 'late_response' "
        "THEN RAISE EXCEPTION 'only late_response may follow outcome_unknown'; END IF; END IF; "
        "RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_llm_call_outcome_sequence BEFORE INSERT ON llm_call_outcome_events "
        "FOR EACH ROW EXECUTE FUNCTION validate_llm_call_outcome_event()"
    )


def _create_restricted_functions() -> None:
    op.execute(
        "CREATE FUNCTION activate_llm_configuration_version"
        "(expected_version uuid, new_version uuid) "
        "RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM llm_configuration_versions WHERE id = new_version) THEN "
        "RAISE EXCEPTION 'new LLM configuration version does not exist'; END IF; "
        "UPDATE llm_configuration_current SET version_id = new_version, updated_at = now() "
        "WHERE singleton AND version_id = expected_version; GET DIAGNOSTICS changed = ROW_COUNT; "
        "RETURN changed = 1; END $$"
    )
    op.execute(
        "CREATE FUNCTION claim_platform_outbox_batch(claimant uuid, batch_size integer, "
        "lease_seconds integer) RETURNS TABLE(event_id uuid, topic text, aggregate_id uuid) "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ BEGIN "
        "RETURN QUERY WITH ready AS (SELECT id FROM platform_outbox_events "
        "WHERE delivered_at IS NULL AND available_at <= now() "
        "AND (claimed_until IS NULL OR claimed_until <= now()) ORDER BY created_at "
        "FOR UPDATE SKIP LOCKED LIMIT GREATEST(1, LEAST(batch_size, 100))) "
        "UPDATE platform_outbox_events outbox SET claimed_by = claimant, "
        "claimed_until = now() + make_interval(secs => GREATEST(1, lease_seconds)), "
        "delivery_attempts = delivery_attempts + 1 FROM ready WHERE outbox.id = ready.id "
        "RETURNING outbox.id, outbox.topic::text, outbox.aggregate_id; END $$"
    )
    op.execute(
        "CREATE FUNCTION acknowledge_platform_outbox(event_id uuid, claimant uuid) RETURNS boolean "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN UPDATE platform_outbox_events SET delivered_at = now(), "
        "claimed_until = NULL WHERE id = event_id AND claimed_by = claimant "
        "AND delivered_at IS NULL; "
        "GET DIAGNOSTICS changed = ROW_COUNT; RETURN changed = 1; END $$"
    )
    op.execute(
        "CREATE FUNCTION release_platform_outbox_claim"
        "(event_id uuid, claimant uuid, error_text text) "
        "RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN UPDATE platform_outbox_events SET claimed_by = NULL, "
        "claimed_until = NULL, last_error = left(error_text, 500) "
        "WHERE id = event_id AND claimed_by = claimant AND delivered_at IS NULL; "
        "GET DIAGNOSTICS changed = ROW_COUNT; RETURN changed = 1; END $$"
    )
    for function in (
        "activate_llm_configuration_version(uuid, uuid)",
        "claim_platform_outbox_batch(uuid, integer, integer)",
        "acknowledge_platform_outbox(uuid, uuid)",
        "release_platform_outbox_claim(uuid, uuid, text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION activate_llm_configuration_version(uuid, uuid) "
        f"TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION claim_platform_outbox_batch(uuid, integer, integer), "
        "acknowledge_platform_outbox(uuid, uuid), "
        "release_platform_outbox_claim(uuid, uuid, text) "
        f"TO {_OUTBOX_DISPATCHER_ROLE}"
    )


def _apply_grants() -> None:
    tables = (
        "job_requirement_schema_versions",
        "prompt_versions",
        "llm_configuration_versions",
        "llm_configuration_current",
        "llm_configuration_attempts",
        "llm_configuration_attempt_events",
        "platform_outbox_events",
        "llm_call_records",
        "llm_call_outcome_events",
    )
    op.execute(f"REVOKE ALL ON TABLE {', '.join(tables)} FROM {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE platform_audit_events FROM {_APP_ROLE}")
    op.execute(
        "GRANT SELECT, INSERT ON TABLE job_requirement_schema_versions, prompt_versions, "
        f"llm_configuration_versions TO {_APP_ROLE}"
    )
    op.execute(f"GRANT SELECT ON TABLE llm_configuration_current TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE llm_configuration_attempts TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE llm_configuration_attempt_events TO {_APP_ROLE}")
    op.execute(f"GRANT INSERT ON TABLE platform_outbox_events TO {_APP_ROLE}")
    op.execute(
        "GRANT SELECT ON TABLE job_requirement_schema_versions, prompt_versions, "
        f"llm_configuration_current TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE llm_configuration_versions, "
        "llm_configuration_attempt_events, llm_call_records, llm_call_outcome_events, "
        f"platform_audit_events TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(
        f"GRANT SELECT, UPDATE ON TABLE llm_configuration_attempts TO {_PLATFORM_WORKER_ROLE}"
    )
    op.execute(f"GRANT INSERT ON TABLE platform_outbox_events TO {_PLATFORM_WORKER_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {', '.join(tables)} FROM {_OUTBOX_DISPATCHER_ROLE}")


def _seed_assets_and_bootstrap() -> None:
    manifest.validate_deployed_assets()
    schema_asset = manifest.JOB_REQUIREMENT_SCHEMA_V1
    prompt_asset = manifest.JOB_REQUIREMENT_PROMPT_V1
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO job_requirement_schema_versions "
            "(id, schema_id, asset_path, sha256, schema_json, field_catalog, "
            "chinese_identity_values, output_limits) "
            "VALUES (:id, :schema_id, :asset_path, :sha256, CAST(:schema_json AS jsonb), "
            "CAST(:field_catalog AS jsonb), CAST(:identity_values AS jsonb), "
            "CAST(:output_limits AS jsonb))"
        ),
        {
            "id": schema_asset.id,
            "schema_id": schema_asset.schema_id,
            "asset_path": f"{schema_asset.package}/{schema_asset.path}",
            "sha256": schema_asset.sha256,
            "schema_json": json.dumps(manifest.read_requirement_schema(schema_asset.id)),
            "field_catalog": json.dumps(schema_asset.field_catalog),
            "identity_values": json.dumps(
                schema_asset.chinese_identity_values,
                ensure_ascii=False,
            ),
            "output_limits": json.dumps(schema_asset.output_limits),
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO prompt_versions "
            "(id, compatible_schema_version_id, asset_path, sha256, content) "
            "VALUES (:id, :schema_id, :asset_path, :sha256, :content)"
        ),
        {
            "id": prompt_asset.id,
            "schema_id": prompt_asset.compatible_schema_version_id,
            "asset_path": f"{prompt_asset.package}/{prompt_asset.path}",
            "sha256": prompt_asset.sha256,
            "content": manifest.read_prompt(prompt_asset.id),
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO llm_configuration_versions "
            "(id, version_number, provider, model, prompt_version_id, "
            "requirement_schema_version_id, temperature, max_output_tokens, "
            "request_timeout_seconds, privacy_routing, source) "
            "VALUES (:id, 1, 'openrouter', 'x-ai/grok-4.5', :prompt_id, :schema_id, "
            "0, 8192, 180, CAST(:privacy AS jsonb), 'migration_bootstrap')"
        ),
        {
            "id": _BOOTSTRAP_VERSION_ID,
            "prompt_id": prompt_asset.id,
            "schema_id": schema_asset.id,
            "privacy": '{"zdr": true, "data_collection": "deny", "require_parameters": true}',
        },
    )
    connection.execute(
        sa.text("INSERT INTO llm_configuration_current (singleton, version_id) VALUES (true, :id)"),
        {"id": _BOOTSTRAP_VERSION_ID},
    )


def upgrade() -> None:
    _create_role(_PLATFORM_WORKER_ROLE)
    _create_role(_OUTBOX_DISPATCHER_ROLE)
    _create_tables()
    _create_invariants()
    _create_restricted_functions()
    _apply_grants()
    _seed_assets_and_bootstrap()


def downgrade() -> None:
    for function in (
        "release_platform_outbox_claim(uuid, uuid, text)",
        "acknowledge_platform_outbox(uuid, uuid)",
        "claim_platform_outbox_batch(uuid, integer, integer)",
        "activate_llm_configuration_version(uuid, uuid)",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    op.drop_table("llm_call_outcome_events")
    op.drop_table("llm_call_records")
    op.drop_index("ix_platform_outbox_events_aggregate_id", table_name="platform_outbox_events")
    op.drop_index("ix_platform_outbox_events_ready", table_name="platform_outbox_events")
    op.drop_table("platform_outbox_events")
    op.drop_table("llm_configuration_attempt_events")
    op.drop_index(
        "uq_llm_configuration_attempts_one_nonterminal",
        table_name="llm_configuration_attempts",
    )
    op.drop_table("llm_configuration_attempts")
    op.drop_table("llm_configuration_current")
    op.drop_table("llm_configuration_versions")
    op.drop_table("prompt_versions")
    op.drop_table("job_requirement_schema_versions")
    for function in (
        "validate_llm_call_outcome_event()",
        "validate_llm_configuration_attempt_event()",
        "validate_llm_configuration_attempt_transition()",
        "reject_immutable_llm_mutation()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    op.execute(f"GRANT UPDATE, DELETE ON TABLE platform_audit_events TO {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE platform_audit_events FROM {_PLATFORM_WORKER_ROLE}")
    for role in (_OUTBOX_DISPATCHER_ROLE, _PLATFORM_WORKER_ROLE):
        op.execute(f"REVOKE {role} FROM CURRENT_USER")
        op.execute(f"REVOKE ALL ON SCHEMA public FROM {role}")
        op.execute(f"DROP ROLE {role}")
