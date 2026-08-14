"""Bind LLM configuration versions by call type and seed search interpretation assets.

Revision ID: 0018_search_interpretation_llm
Revises: 0017_local_talent_identity
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

revision: str = "0018_search_interpretation_llm"
down_revision: str | None = "0017_local_talent_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_PLATFORM_WORKER_ROLE = "relationship_platform_worker"
_NONTERMINAL = "'queued', 'running', 'retry_scheduled', 'cancel_requested'"
_BINDINGS_TABLE = "llm_configuration_call_bindings"
_SEARCH_SCHEMA_TABLE = "search_interpretation_schema_versions"


def upgrade() -> None:
    _create_search_schema_table()
    _extend_prompt_versions()
    _extend_attempts()
    _create_bindings_table()
    _cancel_legacy_attempts()
    _seed_search_assets()
    _backfill_parsing_bindings()
    _apply_grants()


def downgrade() -> None:
    connection = op.get_bind()
    op.execute(f"REVOKE ALL ON TABLE {_BINDINGS_TABLE} FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {_BINDINGS_TABLE} FROM {_PLATFORM_WORKER_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {_SEARCH_SCHEMA_TABLE} FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {_SEARCH_SCHEMA_TABLE} FROM {_PLATFORM_WORKER_ROLE}")
    op.execute(f"DROP TRIGGER trg_{_BINDINGS_TABLE}_immutable ON {_BINDINGS_TABLE}")
    op.drop_table(_BINDINGS_TABLE)
    op.drop_column("llm_configuration_attempts", "probe_progress")
    op.execute("ALTER TABLE prompt_versions DISABLE TRIGGER trg_prompt_versions_immutable")
    connection.execute(
        sa.text("DELETE FROM prompt_versions WHERE id = :id"),
        {"id": manifest.SEARCH_INTERPRETATION_PROMPT_V1.id},
    )
    op.drop_constraint("fk_prompt_versions_output_schema", "prompt_versions", type_="foreignkey")
    op.drop_constraint("ck_prompt_versions_call_type", "prompt_versions", type_="check")
    op.drop_column("prompt_versions", "output_schema_version_id")
    op.drop_column("prompt_versions", "call_type")
    op.execute("ALTER TABLE prompt_versions ENABLE TRIGGER trg_prompt_versions_immutable")
    op.execute(f"DROP TRIGGER trg_{_SEARCH_SCHEMA_TABLE}_immutable ON {_SEARCH_SCHEMA_TABLE}")
    op.drop_table(_SEARCH_SCHEMA_TABLE)


def _create_search_schema_table() -> None:
    op.create_table(
        _SEARCH_SCHEMA_TABLE,
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("schema_id", sa.String(length=200), nullable=False),
        sa.Column("asset_path", sa.String(length=300), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compatible_schema_version_id", sa.String(length=100), nullable=False),
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
        sa.UniqueConstraint("schema_id"),
        sa.UniqueConstraint("sha256"),
    )
    op.execute(
        f"CREATE TRIGGER trg_{_SEARCH_SCHEMA_TABLE}_immutable "
        f"BEFORE UPDATE OR DELETE ON {_SEARCH_SCHEMA_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )


def _extend_prompt_versions() -> None:
    op.add_column(
        "prompt_versions",
        sa.Column(
            "call_type",
            sa.String(length=40),
            server_default="job_requirement_parsing",
            nullable=False,
        ),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("output_schema_version_id", sa.String(length=100), nullable=True),
    )
    op.create_check_constraint(
        "ck_prompt_versions_call_type",
        "prompt_versions",
        "call_type IN ('job_requirement_parsing', 'search_interpretation')",
    )
    op.create_foreign_key(
        "fk_prompt_versions_output_schema",
        "prompt_versions",
        _SEARCH_SCHEMA_TABLE,
        ["output_schema_version_id"],
        ["id"],
    )


def _extend_attempts() -> None:
    op.add_column(
        "llm_configuration_attempts",
        sa.Column(
            "probe_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def _create_bindings_table() -> None:
    op.create_table(
        _BINDINGS_TABLE,
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("call_type", sa.String(length=40), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=100), nullable=False),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "call_type IN ('job_requirement_parsing', 'search_interpretation')",
            name="ck_llm_configuration_call_bindings_type",
        ),
        sa.CheckConstraint(
            "("
            "call_type = 'job_requirement_parsing' "
            "AND request_timeout_seconds BETWEEN 30 AND 300"
            ") OR ("
            "call_type = 'search_interpretation' "
            "AND request_timeout_seconds BETWEEN 5 AND 30"
            ")",
            name="ck_llm_configuration_call_bindings_timeout",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"],
            ["llm_configuration_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"]),
        sa.PrimaryKeyConstraint("configuration_version_id", "call_type"),
    )
    op.execute(
        f"CREATE TRIGGER trg_{_BINDINGS_TABLE}_immutable "
        f"BEFORE UPDATE OR DELETE ON {_BINDINGS_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_llm_mutation()"
    )


def _cancel_legacy_attempts() -> None:
    op.execute(
        "UPDATE llm_configuration_attempts "
        "SET status = 'cancelled', "
        "error_code = 'incompatible_candidate_snapshot', "
        "lease_token = NULL, "
        "lease_expires_at = NULL, "
        "last_heartbeat_at = NULL, "
        "next_attempt_at = NULL "
        f"WHERE status IN ({_NONTERMINAL}) "
        "AND NOT (candidate_snapshot ? 'call_bindings')"
    )


def _seed_search_assets() -> None:
    manifest.validate_deployed_assets()
    schema = manifest.SEARCH_INTERPRETATION_SCHEMA_V1
    prompt = manifest.SEARCH_INTERPRETATION_PROMPT_V1
    connection = op.get_bind()
    connection.execute(
        sa.text(
            f"INSERT INTO {_SEARCH_SCHEMA_TABLE} "
            "(id, schema_id, asset_path, sha256, schema_json, compatible_schema_version_id) "
            "VALUES (:id, :schema_id, :asset_path, :sha256, CAST(:schema_json AS jsonb), "
            ":compatible_schema_version_id)"
        ),
        {
            "asset_path": f"{schema.package}/{schema.path}",
            "compatible_schema_version_id": schema.compatible_schema_version_id,
            "id": schema.id,
            "schema_id": schema.schema_id,
            "schema_json": json.dumps(
                manifest.read_search_interpretation_schema(schema.id),
                ensure_ascii=False,
            ),
            "sha256": schema.sha256,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO prompt_versions "
            "(id, compatible_schema_version_id, call_type, output_schema_version_id, "
            "asset_path, sha256, content) "
            "VALUES (:id, :schema_id, :call_type, :output_schema_id, :asset_path, "
            ":sha256, :content)"
        ),
        {
            "asset_path": f"{prompt.package}/{prompt.path}",
            "call_type": prompt.call_type,
            "content": manifest.read_prompt(prompt.id),
            "id": prompt.id,
            "output_schema_id": prompt.output_schema_version_id,
            "schema_id": prompt.compatible_schema_version_id,
            "sha256": prompt.sha256,
        },
    )


def _backfill_parsing_bindings() -> None:
    op.execute(
        f"INSERT INTO {_BINDINGS_TABLE} "
        "(configuration_version_id, call_type, prompt_version_id, request_timeout_seconds) "
        "SELECT id, 'job_requirement_parsing', prompt_version_id, request_timeout_seconds "
        "FROM llm_configuration_versions"
    )


def _apply_grants() -> None:
    op.execute(f"GRANT SELECT ON TABLE {_SEARCH_SCHEMA_TABLE}, {_BINDINGS_TABLE} TO {_APP_ROLE}")
    op.execute(f"GRANT INSERT ON TABLE {_BINDINGS_TABLE} TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT ON TABLE {_SEARCH_SCHEMA_TABLE} TO {_PLATFORM_WORKER_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {_BINDINGS_TABLE} TO {_PLATFORM_WORKER_ROLE}")
