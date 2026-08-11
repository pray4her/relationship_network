"""Tenant requirement input snapshots, parsing tasks, and validated drafts.

Revision ID: 0012_requirement_draft
Revises: 0011_llm_call_audit
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from relationship_network_api.llm_assets import manifest

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0012_requirement_draft"
down_revision: str | None = "0011_llm_call_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_OUTBOX_DISPATCHER_ROLE = "relationship_outbox_dispatcher"
_TASK_SCHEDULER_ROLE = "relationship_requirement_scheduler"
_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"
_NONTERMINAL = "'queued', 'running', 'retry_scheduled', 'cancel_requested'"
_TASK_STATUSES = f"{_NONTERMINAL}, 'succeeded', 'failed', 'cancelled'"


def _create_role(role: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN; "
        "END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT {role} TO CURRENT_USER")


def _add_v2_assets_and_input_limit() -> None:
    op.add_column(
        "llm_configuration_versions",
        sa.Column(
            "input_character_limit",
            sa.Integer(),
            server_default="100000",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_llm_configuration_versions_input_limit",
        "llm_configuration_versions",
        "input_character_limit = 100000",
    )
    manifest.validate_deployed_assets()
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V2
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V2
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
            "asset_path": f"{schema.package}/{schema.path}",
            "field_catalog": json.dumps(schema.field_catalog),
            "id": schema.id,
            "identity_values": json.dumps(schema.chinese_identity_values, ensure_ascii=False),
            "output_limits": json.dumps(schema.output_limits),
            "schema_id": schema.schema_id,
            "schema_json": json.dumps(
                manifest.read_requirement_schema(schema.id), ensure_ascii=False
            ),
            "sha256": schema.sha256,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO prompt_versions "
            "(id, compatible_schema_version_id, asset_path, sha256, content) "
            "VALUES (:id, :schema_id, :asset_path, :sha256, :content)"
        ),
        {
            "asset_path": f"{prompt.package}/{prompt.path}",
            "content": manifest.read_prompt(prompt.id),
            "id": prompt.id,
            "schema_id": prompt.compatible_schema_version_id,
            "sha256": prompt.sha256,
        },
    )


def _create_tables() -> None:
    op.create_unique_constraint("uq_jobs_id_tenant", "jobs", ["id", "tenant_id"])
    op.create_unique_constraint(
        "uq_job_materials_id_tenant_job",
        "job_materials",
        ["id", "tenant_id", "job_id"],
    )
    op.create_table(
        "job_requirement_input_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("total_characters", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("total_characters >= 0", name="ck_requirement_snapshots_length"),
        sa.ForeignKeyConstraint(
            ["job_id", "tenant_id"],
            ["jobs.id", "jobs.tenant_id"],
            name="fk_requirement_snapshots_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_requirement_snapshots_id_tenant"),
    )
    op.create_index(
        "ix_requirement_snapshots_tenant_job",
        "job_requirement_input_snapshots",
        ["tenant_id", "job_id"],
    )
    op.create_table(
        "job_requirement_input_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("sent_text", sa.Text(), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("sent_sha256", sa.String(length=64), nullable=False),
        sa.Column("unicode_characters", sa.Integer(), nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=True),
        sa.Column(
            "edited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_requirement_sources_position"),
        sa.CheckConstraint("unicode_characters > 0", name="ck_requirement_sources_length"),
        sa.CheckConstraint(
            "source_kind IN ('job-description', 'job-material')",
            name="ck_requirement_sources_kind",
        ),
        sa.CheckConstraint(
            "(source_kind = 'job-description' AND material_id IS NULL) OR "
            "(source_kind = 'job-material' AND material_id IS NOT NULL)",
            name="ck_requirement_sources_material",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "tenant_id"],
            ["job_requirement_input_snapshots.id", "job_requirement_input_snapshots.tenant_id"],
            name="fk_requirement_sources_snapshot_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id", "tenant_id", "job_id"],
            ["job_materials.id", "job_materials.tenant_id", "job_materials.job_id"],
            name="fk_requirement_sources_material_tenant_job",
        ),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "source_id", name="uq_requirement_sources_snapshot_source"
        ),
        sa.UniqueConstraint("snapshot_id", "position", name="uq_requirement_sources_position"),
    )
    op.create_index(
        "ix_requirement_sources_tenant_snapshot",
        "job_requirement_input_sources",
        ["tenant_id", "snapshot_id"],
    )
    op.create_table(
        "job_requirement_parsing_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("input_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("effective_request_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("external_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("structured_invalid_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"status IN ({_TASK_STATUSES})", name="ck_requirement_tasks_status"),
        sa.CheckConstraint(
            "external_call_count BETWEEN 0 AND 3", name="ck_requirement_tasks_call_budget"
        ),
        sa.CheckConstraint(
            "structured_invalid_count BETWEEN 0 AND 2",
            name="ck_requirement_tasks_structured_invalid_budget",
        ),
        sa.CheckConstraint(
            "((status IN ('running', 'cancel_requested')) = "
            "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND last_heartbeat_at IS NOT NULL))",
            name="ck_requirement_tasks_lease_fields",
        ),
        sa.CheckConstraint(
            "((status = 'retry_scheduled') = (next_attempt_at IS NOT NULL))",
            name="ck_requirement_tasks_retry_fields",
        ),
        sa.CheckConstraint(
            "((status IN ('succeeded', 'failed', 'cancelled')) = (completed_at IS NOT NULL))",
            name="ck_requirement_tasks_completion_fields",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "tenant_id"],
            ["jobs.id", "jobs.tenant_id"],
            name="fk_requirement_tasks_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["input_snapshot_id", "tenant_id"],
            ["job_requirement_input_snapshots.id", "job_requirement_input_snapshots.tenant_id"],
            name="fk_requirement_tasks_snapshot_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_requirement_tasks_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_requirement_tasks_tenant_idempotency",
        ),
    )
    op.create_index(
        "uq_requirement_tasks_one_nonterminal",
        "job_requirement_parsing_tasks",
        ["tenant_id", "job_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_NONTERMINAL})"),
    )
    op.create_index(
        "ix_requirement_tasks_tenant_job_created",
        "job_requirement_parsing_tasks",
        ["tenant_id", "job_id", "created_at"],
    )
    op.create_index(
        "ix_requirement_tasks_retry_due",
        "job_requirement_parsing_tasks",
        ["next_attempt_at"],
        postgresql_where=sa.text("status = 'retry_scheduled'"),
    )
    op.create_index(
        "ix_requirement_tasks_lease_due",
        "job_requirement_parsing_tasks",
        ["lease_expires_at"],
        postgresql_where=sa.text("status IN ('running', 'cancel_requested')"),
    )
    op.create_table(
        "job_requirement_parsing_task_events",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("sequence_number > 0", name="ck_requirement_task_events_sequence"),
        sa.ForeignKeyConstraint(
            ["task_id", "tenant_id"],
            ["job_requirement_parsing_tasks.id", "job_requirement_parsing_tasks.tenant_id"],
            name="fk_requirement_task_events_task_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "sequence_number"),
    )
    op.create_index(
        "ix_requirement_task_events_tenant_task",
        "job_requirement_parsing_task_events",
        ["tenant_id", "task_id"],
    )
    op.create_table(
        "job_requirement_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("input_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_schema_version_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="editable", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            "status IN ('editable', 'confirmed', 'replaced', 'abandoned')",
            name="ck_requirement_drafts_status",
        ),
        sa.CheckConstraint("revision > 0", name="ck_requirement_drafts_revision"),
        sa.ForeignKeyConstraint(
            ["job_id", "tenant_id"],
            ["jobs.id", "jobs.tenant_id"],
            name="fk_requirement_drafts_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "tenant_id"],
            ["job_requirement_parsing_tasks.id", "job_requirement_parsing_tasks.tenant_id"],
            name="fk_requirement_drafts_task_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["input_snapshot_id", "tenant_id"],
            ["job_requirement_input_snapshots.id", "job_requirement_input_snapshots.tenant_id"],
            name="fk_requirement_drafts_snapshot_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_schema_version_id"], ["job_requirement_schema_versions.id"]
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_requirement_drafts_task"),
    )
    op.create_index(
        "uq_requirement_drafts_one_editable",
        "job_requirement_drafts",
        ["tenant_id", "job_id"],
        unique=True,
        postgresql_where=sa.text("status = 'editable'"),
    )
    op.create_table(
        "tenant_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("job_requirement_parsing_task_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["job_requirement_parsing_task_id", "tenant_id"],
            ["job_requirement_parsing_tasks.id", "job_requirement_parsing_tasks.tenant_id"],
            name="fk_tenant_outbox_task_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_outbox_events_tenant_id", "tenant_outbox_events", ["tenant_id"])
    op.create_index(
        "ix_tenant_outbox_events_ready",
        "tenant_outbox_events",
        ["available_at"],
        postgresql_where=sa.text("delivered_at IS NULL"),
    )


def _extend_llm_call_tenant_references() -> None:
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        "(scope = 'platform' AND tenant_id IS NULL AND call_type = 'config_probe' "
        "AND platform_attempt_id IS NOT NULL AND job_requirement_parsing_task_id IS NULL "
        "AND configuration_version_id IS NULL AND input_snapshot_id IS NULL) OR "
        "(scope = 'tenant' AND tenant_id IS NOT NULL "
        "AND call_type = 'job_requirement_parsing' AND platform_attempt_id IS NULL "
        "AND job_requirement_parsing_task_id IS NOT NULL "
        "AND configuration_version_id IS NOT NULL AND input_snapshot_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_llm_call_records_tenant_task",
        "llm_call_records",
        "job_requirement_parsing_tasks",
        ["job_requirement_parsing_task_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_llm_call_records_tenant_snapshot",
        "llm_call_records",
        "job_requirement_input_snapshots",
        ["input_snapshot_id", "tenant_id"],
        ["id", "tenant_id"],
    )


def _create_invariants() -> None:
    for table in (
        "job_requirement_input_snapshots",
        "job_requirement_input_sources",
        "job_requirement_parsing_task_events",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
        )
    op.execute(
        "CREATE FUNCTION validate_requirement_task_transition() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF NEW.tenant_id <> OLD.tenant_id OR NEW.job_id <> OLD.job_id "
        "OR NEW.input_snapshot_id <> OLD.input_snapshot_id "
        "OR NEW.configuration_version_id <> OLD.configuration_version_id "
        "OR NEW.idempotency_key <> OLD.idempotency_key "
        "OR NEW.effective_request_sha256 <> OLD.effective_request_sha256 "
        "OR NEW.created_by IS DISTINCT FROM OLD.created_by "
        "OR NEW.created_at <> OLD.created_at THEN "
        "RAISE EXCEPTION 'immutable requirement task fields cannot be changed'; END IF; "
        "IF OLD.status IN ('succeeded', 'failed', 'cancelled') THEN "
        "RAISE EXCEPTION 'terminal requirement task cannot be changed'; END IF; "
        "IF NEW.status <> OLD.status AND NOT ("
        "(OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled')) OR "
        "(OLD.status = 'running' AND NEW.status IN "
        "('retry_scheduled', 'succeeded', 'failed', 'cancel_requested')) OR "
        "(OLD.status = 'running' AND NEW.status = 'queued' "
        "AND OLD.lease_expires_at <= now()) OR "
        "(OLD.status = 'retry_scheduled' AND NEW.status IN ('queued', 'cancelled')) OR "
        "(OLD.status = 'cancel_requested' AND NEW.status = 'cancelled')) THEN "
        "RAISE EXCEPTION 'illegal requirement task transition: % -> %', OLD.status, NEW.status; "
        "END IF; "
        "IF OLD.status IN ('running', 'cancel_requested') "
        "AND NEW.status IN ('running', 'cancel_requested') "
        "AND NEW.lease_token IS DISTINCT FROM OLD.lease_token THEN "
        "RAISE EXCEPTION 'requirement task lease token cannot be replaced'; END IF; "
        "IF NEW.status IN ('running', 'cancel_requested') AND "
        "(NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL "
        "OR NEW.last_heartbeat_at IS NULL) THEN "
        "RAISE EXCEPTION 'running requirement task requires a complete lease'; END IF; "
        "IF NEW.status NOT IN ('running', 'cancel_requested') AND "
        "(NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL "
        "OR NEW.last_heartbeat_at IS NOT NULL) THEN "
        "RAISE EXCEPTION 'non-running requirement task cannot retain a lease'; END IF; "
        "IF NEW.status = 'retry_scheduled' AND NEW.next_attempt_at IS NULL THEN "
        "RAISE EXCEPTION 'scheduled retry requires next_attempt_at'; END IF; "
        "IF NEW.status <> 'retry_scheduled' AND NEW.next_attempt_at IS NOT NULL THEN "
        "RAISE EXCEPTION 'only scheduled retry may have next_attempt_at'; END IF; "
        "IF NEW.status IN ('succeeded', 'failed', 'cancelled') "
        "AND NEW.completed_at IS NULL THEN "
        "RAISE EXCEPTION 'terminal requirement task requires completed_at'; END IF; "
        "IF NEW.status NOT IN ('succeeded', 'failed', 'cancelled') "
        "AND NEW.completed_at IS NOT NULL THEN "
        "RAISE EXCEPTION 'nonterminal requirement task cannot have completed_at'; END IF; "
        "IF NEW.status = 'failed' AND NEW.error_code IS NULL THEN "
        "RAISE EXCEPTION 'failed requirement task requires error_code'; END IF; "
        "NEW.updated_at = now(); RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_requirement_task_transition BEFORE UPDATE "
        "ON job_requirement_parsing_tasks FOR EACH ROW "
        "EXECUTE FUNCTION validate_requirement_task_transition()"
    )
    op.execute(
        "CREATE FUNCTION validate_requirement_task_event() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ DECLARE expected_sequence integer; current_status text; BEGIN "
        "SELECT status INTO current_status FROM job_requirement_parsing_tasks "
        "WHERE id = NEW.task_id AND tenant_id = NEW.tenant_id FOR UPDATE; "
        "IF current_status IS NULL THEN RAISE EXCEPTION 'requirement task not found'; END IF; "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO expected_sequence "
        "FROM job_requirement_parsing_task_events WHERE task_id = NEW.task_id; "
        "IF NEW.sequence_number <> expected_sequence THEN "
        "RAISE EXCEPTION 'requirement task event sequence must be %', expected_sequence; END IF; "
        "IF NEW.event_type <> current_status THEN "
        "RAISE EXCEPTION 'requirement task event must match current status'; END IF; "
        "PERFORM pg_notify('job_requirement_parsing_task_events', "
        "NEW.task_id::text || ':' || NEW.sequence_number::text); RETURN NEW; END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_requirement_task_event_sequence BEFORE INSERT "
        "ON job_requirement_parsing_task_events FOR EACH ROW "
        "EXECUTE FUNCTION validate_requirement_task_event()"
    )


def _enable_rls_and_grants() -> None:
    tables = (
        "job_requirement_input_snapshots",
        "job_requirement_input_sources",
        "job_requirement_parsing_tasks",
        "job_requirement_parsing_task_events",
        "job_requirement_drafts",
        "tenant_outbox_events",
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} TO {_APP_ROLE} "
            f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
            f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
        )
    op.execute(f"REVOKE ALL ON TABLE {', '.join(tables)} FROM {_APP_ROLE}")
    op.execute(
        "GRANT SELECT, INSERT ON TABLE job_requirement_input_snapshots, "
        "job_requirement_input_sources, job_requirement_parsing_task_events "
        f"TO {_APP_ROLE}"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE job_requirement_parsing_tasks, "
        f"job_requirement_drafts TO {_APP_ROLE}"
    )
    op.execute(f"GRANT INSERT ON TABLE tenant_outbox_events TO {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {', '.join(tables)} FROM {_OUTBOX_DISPATCHER_ROLE}")


def _create_tenant_outbox_functions() -> None:
    op.execute(
        "CREATE FUNCTION claim_tenant_outbox_batch(claimant uuid, batch_size integer, "
        "lease_seconds integer) RETURNS TABLE(event_id uuid, tenant_id uuid, topic text, "
        "aggregate_id uuid, task_id uuid) "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ BEGIN "
        "RETURN QUERY WITH ready AS (SELECT id FROM tenant_outbox_events "
        "WHERE delivered_at IS NULL AND available_at <= now() "
        "AND (claimed_until IS NULL OR claimed_until <= now()) ORDER BY created_at "
        "FOR UPDATE SKIP LOCKED LIMIT GREATEST(1, LEAST(batch_size, 100))) "
        "UPDATE tenant_outbox_events outbox SET claimed_by = claimant, "
        "claimed_until = now() + make_interval(secs => GREATEST(1, lease_seconds)), "
        "delivery_attempts = delivery_attempts + 1 FROM ready WHERE outbox.id = ready.id "
        "RETURNING outbox.id, outbox.tenant_id, outbox.topic::text, outbox.aggregate_id, "
        "outbox.job_requirement_parsing_task_id; END $$"
    )
    op.execute(
        "CREATE FUNCTION acknowledge_tenant_outbox(event_id uuid, claimant uuid) RETURNS boolean "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN UPDATE tenant_outbox_events SET delivered_at = now(), "
        "claimed_until = NULL WHERE id = event_id AND claimed_by = claimant "
        "AND delivered_at IS NULL; GET DIAGNOSTICS changed = ROW_COUNT; "
        "RETURN changed = 1; END $$"
    )
    op.execute(
        "CREATE FUNCTION release_tenant_outbox_claim"
        "(event_id uuid, claimant uuid, error_text text) RETURNS boolean "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE changed integer; BEGIN UPDATE tenant_outbox_events SET claimed_by = NULL, "
        "claimed_until = NULL, last_error = left(error_text, 500) "
        "WHERE id = event_id AND claimed_by = claimant AND delivered_at IS NULL; "
        "GET DIAGNOSTICS changed = ROW_COUNT; RETURN changed = 1; END $$"
    )
    op.execute(
        "CREATE FUNCTION enqueue_delayed_requirement_task"
        "(requested_task_id uuid, requested_tenant_id uuid, delay_seconds integer) "
        "RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER "
        "SET search_path = public, pg_temp AS $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM job_requirement_parsing_tasks tasks "
        "WHERE tasks.id = requested_task_id AND tasks.tenant_id = requested_tenant_id "
        "AND tasks.status = 'queued') THEN RETURN false; END IF; "
        "IF EXISTS (SELECT 1 FROM tenant_outbox_events outbox "
        "WHERE outbox.job_requirement_parsing_task_id = requested_task_id "
        "AND outbox.tenant_id = requested_tenant_id AND outbox.delivered_at IS NULL "
        "AND outbox.available_at > now()) THEN RETURN false; END IF; "
        "INSERT INTO tenant_outbox_events "
        "(id, tenant_id, topic, aggregate_id, job_requirement_parsing_task_id, available_at) "
        "VALUES (gen_random_uuid(), requested_tenant_id, "
        "'job_requirement_parsing.process', requested_task_id, requested_task_id, "
        "now() + make_interval(secs => GREATEST(1, delay_seconds))); RETURN true; END $$"
    )
    signatures = (
        "claim_tenant_outbox_batch(uuid, integer, integer)",
        "acknowledge_tenant_outbox(uuid, uuid)",
        "release_tenant_outbox_claim(uuid, uuid, text)",
        "enqueue_delayed_requirement_task(uuid, uuid, integer)",
    )
    for signature in signatures:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {_OUTBOX_DISPATCHER_ROLE}")
    op.execute(
        "REVOKE ALL ON FUNCTION enqueue_delayed_requirement_task(uuid, uuid, integer) "
        f"FROM {_OUTBOX_DISPATCHER_ROLE}"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION enqueue_delayed_requirement_task(uuid, uuid, integer) "
        f"TO {_APP_ROLE}"
    )


def _create_task_scheduler_functions() -> None:
    op.execute(
        "CREATE FUNCTION schedule_due_requirement_tasks(batch_size integer) RETURNS integer "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE task_row record; next_sequence integer; changed integer := 0; BEGIN "
        "FOR task_row IN SELECT id, tenant_id FROM job_requirement_parsing_tasks "
        "WHERE status = 'retry_scheduled' AND next_attempt_at <= now() "
        "ORDER BY next_attempt_at FOR UPDATE SKIP LOCKED "
        "LIMIT GREATEST(1, LEAST(batch_size, 100)) LOOP "
        "UPDATE job_requirement_parsing_tasks SET status = 'queued', next_attempt_at = NULL "
        "WHERE id = task_row.id; "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO next_sequence "
        "FROM job_requirement_parsing_task_events WHERE task_id = task_row.id; "
        "INSERT INTO job_requirement_parsing_task_events "
        "(task_id, sequence_number, tenant_id, event_type, payload) VALUES "
        "(task_row.id, next_sequence, task_row.tenant_id, 'queued', '{}'::jsonb); "
        "INSERT INTO tenant_outbox_events "
        "(id, tenant_id, topic, aggregate_id, job_requirement_parsing_task_id) VALUES "
        "(gen_random_uuid(), task_row.tenant_id, 'job_requirement_parsing.process', "
        "task_row.id, task_row.id); changed := changed + 1; END LOOP; RETURN changed; END $$"
    )
    op.execute(
        "CREATE FUNCTION recover_expired_requirement_tasks(batch_size integer) RETURNS integer "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$ "
        "DECLARE task_row record; call_row record; next_sequence integer; "
        "changed integer := 0; BEGIN FOR task_row IN "
        "SELECT id, tenant_id, status FROM job_requirement_parsing_tasks "
        "WHERE status IN ('running', 'cancel_requested') AND lease_expires_at <= now() "
        "ORDER BY lease_expires_at FOR UPDATE SKIP LOCKED "
        "LIMIT GREATEST(1, LEAST(batch_size, 100)) LOOP "
        "IF task_row.status = 'cancel_requested' THEN "
        "UPDATE job_requirement_parsing_tasks SET status = 'cancelled', completed_at = now(), "
        "lease_token = NULL, lease_expires_at = NULL, last_heartbeat_at = NULL "
        "WHERE id = task_row.id; "
        "ELSE SELECT calls.id, calls.scope, calls.tenant_id INTO call_row "
        "FROM llm_call_records calls WHERE calls.job_requirement_parsing_task_id = task_row.id "
        "ORDER BY calls.request_number DESC LIMIT 1; "
        "IF call_row.id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM llm_call_outcome_events outcomes WHERE outcomes.call_id = call_row.id) "
        "THEN INSERT INTO llm_call_outcome_events "
        "(call_id, sequence_number, scope, tenant_id, outcome, category) VALUES "
        "(call_row.id, 1, call_row.scope, call_row.tenant_id, "
        "'outcome_unknown', 'lease_expired'); END IF; "
        "UPDATE job_requirement_parsing_tasks SET status = 'queued', "
        "error_code = 'requirement_generation_unavailable', lease_token = NULL, "
        "lease_expires_at = NULL, last_heartbeat_at = NULL WHERE id = task_row.id; END IF; "
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO next_sequence "
        "FROM job_requirement_parsing_task_events WHERE task_id = task_row.id; "
        "INSERT INTO job_requirement_parsing_task_events "
        "(task_id, sequence_number, tenant_id, event_type, payload) VALUES "
        "(task_row.id, next_sequence, task_row.tenant_id, "
        "CASE WHEN task_row.status = 'cancel_requested' THEN 'cancelled' ELSE 'queued' END, "
        "CASE WHEN task_row.status = 'cancel_requested' THEN '{}'::jsonb ELSE "
        "jsonb_build_object('error_code', 'requirement_generation_unavailable', "
        "'retryable', true) END); "
        "IF task_row.status <> 'cancel_requested' THEN INSERT INTO tenant_outbox_events "
        "(id, tenant_id, topic, aggregate_id, job_requirement_parsing_task_id) VALUES "
        "(gen_random_uuid(), task_row.tenant_id, 'job_requirement_parsing.process', "
        "task_row.id, task_row.id); END IF; changed := changed + 1; END LOOP; "
        "RETURN changed; END $$"
    )
    for signature in (
        "schedule_due_requirement_tasks(integer)",
        "recover_expired_requirement_tasks(integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {_TASK_SCHEDULER_ROLE}")


def upgrade() -> None:
    _create_role(_TASK_SCHEDULER_ROLE)
    _add_v2_assets_and_input_limit()
    _create_tables()
    _extend_llm_call_tenant_references()
    _create_invariants()
    _enable_rls_and_grants()
    _create_tenant_outbox_functions()
    _create_task_scheduler_functions()


def downgrade() -> None:
    for signature in (
        "recover_expired_requirement_tasks(integer)",
        "schedule_due_requirement_tasks(integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {_TASK_SCHEDULER_ROLE}")
        op.execute(f"DROP FUNCTION {signature}")
    for signature in (
        "enqueue_delayed_requirement_task(uuid, uuid, integer)",
        "release_tenant_outbox_claim(uuid, uuid, text)",
        "acknowledge_tenant_outbox(uuid, uuid)",
        "claim_tenant_outbox_batch(uuid, integer, integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {_OUTBOX_DISPATCHER_ROLE}")
        op.execute(f"DROP FUNCTION {signature}")
    op.drop_constraint(
        "fk_llm_call_records_tenant_snapshot", "llm_call_records", type_="foreignkey"
    )
    op.drop_constraint("fk_llm_call_records_tenant_task", "llm_call_records", type_="foreignkey")
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        "(scope = 'platform' AND tenant_id IS NULL AND call_type = 'config_probe' "
        "AND platform_attempt_id IS NOT NULL AND job_requirement_parsing_task_id IS NULL) OR "
        "(scope = 'tenant' AND tenant_id IS NOT NULL "
        "AND call_type = 'job_requirement_parsing' AND platform_attempt_id IS NULL "
        "AND job_requirement_parsing_task_id IS NOT NULL)",
    )
    op.execute(
        "DROP TRIGGER trg_requirement_task_event_sequence ON job_requirement_parsing_task_events"
    )
    op.execute("DROP FUNCTION validate_requirement_task_event()")
    op.execute("DROP TRIGGER trg_requirement_task_transition ON job_requirement_parsing_tasks")
    op.execute("DROP FUNCTION validate_requirement_task_transition()")
    for table in (
        "job_requirement_input_snapshots",
        "job_requirement_input_sources",
        "job_requirement_parsing_task_events",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
    for table in (
        "tenant_outbox_events",
        "job_requirement_drafts",
        "job_requirement_parsing_task_events",
        "job_requirement_parsing_tasks",
        "job_requirement_input_sources",
        "job_requirement_input_snapshots",
    ):
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
    op.drop_constraint("uq_job_materials_id_tenant_job", "job_materials", type_="unique")
    op.drop_constraint("uq_jobs_id_tenant", "jobs", type_="unique")
    connection = op.get_bind()
    op.execute("ALTER TABLE prompt_versions DISABLE TRIGGER trg_prompt_versions_immutable")
    connection.execute(
        sa.text("DELETE FROM prompt_versions WHERE id = :id"),
        {"id": manifest.JOB_REQUIREMENT_PROMPT_V2.id},
    )
    op.execute("ALTER TABLE prompt_versions ENABLE TRIGGER trg_prompt_versions_immutable")
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "DISABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )
    connection.execute(
        sa.text("DELETE FROM job_requirement_schema_versions WHERE id = :id"),
        {"id": manifest.JOB_REQUIREMENT_SCHEMA_V2.id},
    )
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "ENABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )
    op.drop_constraint(
        "ck_llm_configuration_versions_input_limit",
        "llm_configuration_versions",
        type_="check",
    )
    op.drop_column("llm_configuration_versions", "input_character_limit")
    op.execute(f"REVOKE {_TASK_SCHEDULER_ROLE} FROM CURRENT_USER")
    op.execute(f"REVOKE ALL ON SCHEMA public FROM {_TASK_SCHEDULER_ROLE}")
    op.execute(f"DROP ROLE {_TASK_SCHEDULER_ROLE}")
