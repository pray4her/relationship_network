"""Natural-language search runs, hit snapshots, and search-interpretation call records.

Adds the immutable tenant-scoped search run and its frozen hit snapshots, and
extends ``llm_call_records`` so tenant-scoped search interpretation calls can be
audited under ADR 0022.

Revision ID: 0019_natural_language_search_run
Revises: 0018_search_interpretation_llm
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_natural_language_search_run"
down_revision: str | None = "0018_search_interpretation_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"

_RUNS_TABLE = "natural_language_search_runs"
_SNAPSHOTS_TABLE = "search_hit_snapshots"

_TENANT_MATCH = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
_PLATFORM_ADMIN_MATCH = "nullif(current_setting('app.platform_admin', true), '') = 'on'"

_SCOPE_KEY_CHECK = " ".join(  # noqa: FLY002
    (
        "(scope = 'platform' AND tenant_id IS NULL AND call_type = 'config_probe'",
        "AND platform_attempt_id IS NOT NULL AND job_requirement_parsing_task_id IS NULL",
        "AND configuration_version_id IS NULL AND input_snapshot_id IS NULL) OR",
        "(scope = 'tenant' AND tenant_id IS NOT NULL",
        "AND call_type = 'job_requirement_parsing' AND platform_attempt_id IS NULL",
        "AND job_requirement_parsing_task_id IS NOT NULL",
        "AND configuration_version_id IS NOT NULL AND input_snapshot_id IS NOT NULL) OR",
        "(scope = 'tenant' AND tenant_id IS NOT NULL",
        "AND call_type = 'search_interpretation' AND platform_attempt_id IS NULL",
        "AND search_run_id IS NOT NULL AND job_requirement_parsing_task_id IS NULL",
        "AND configuration_version_id IS NOT NULL AND input_snapshot_id IS NULL)",
    )
)


def _enable_tenant_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH}) "
        f"WITH CHECK ({_TENANT_MATCH} OR {_PLATFORM_ADMIN_MATCH})"
    )


def _create_runs_table() -> None:
    op.create_table(
        _RUNS_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=40), nullable=True),
        sa.Column("utterance", sa.Text(), nullable=False),
        sa.Column("utterance_sha256", sa.String(length=64), nullable=False),
        sa.Column("utterance_length", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("llm_configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("search_contract_version", sa.String(length=20), nullable=False),
        sa.Column("data_version", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=200), nullable=True),
        sa.Column(
            "has_research_topic",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "search_interpretation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("usage_reservation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'succeeded', 'failed')",
            name="ck_search_runs_status",
        ),
        sa.CheckConstraint(
            "failure_reason IN ('interpretation_invalid', 'interpretation_error', 'search_base_error', 'search_base_timeout', 'quota_exceeded')",  # noqa: E501
            name="ck_search_runs_failure_reason",
        ),
        sa.CheckConstraint("utterance_length >= 0", name="ck_search_runs_utterance_length"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["llm_configuration_version_id"],
            ["llm_configuration_versions.id"],
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_search_runs_tenant_idempotency"
        ),
    )
    op.create_index("ix_search_runs_tenant_id", _RUNS_TABLE, ["tenant_id"])
    op.create_index("ix_search_runs_tenant_created", _RUNS_TABLE, ["tenant_id", "created_at"])
    op.create_index(
        "uq_search_runs_tenant_nonterminal",
        _RUNS_TABLE,
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def _create_snapshots_table() -> None:
    op.create_table(
        _SNAPSHOTS_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("search_run_id", sa.Uuid(), nullable=False),
        sa.Column("local_talent_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_person_id", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("current_affiliation", sa.String(length=300), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("chinese_identity", sa.String(length=20), nullable=False),
        sa.Column("h_index", sa.Integer(), nullable=False),
        sa.Column("total_citations", sa.Integer(), nullable=False),
        sa.Column("qs_top200_rank", sa.Integer(), nullable=True),
        sa.Column("world_top500_rank", sa.Integer(), nullable=True),
        sa.Column("has_contact", sa.Boolean(), nullable=True),
        sa.Column("data_version", sa.String(length=100), nullable=False),
        sa.Column(
            "hit_publications",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("sort_position", sa.Integer(), nullable=False),
        sa.CheckConstraint("h_index >= 0", name="ck_search_hit_snapshots_h_index"),
        sa.CheckConstraint("total_citations >= 0", name="ck_search_hit_snapshots_total_citations"),
        sa.CheckConstraint(
            "chinese_identity IN ('国内华人', '海外华人', '外国人')",
            name="ck_search_hit_snapshots_chinese_identity",
        ),
        sa.CheckConstraint("sort_position >= 0", name="ck_search_hit_snapshots_sort_position"),
        sa.ForeignKeyConstraint(["local_talent_id"], ["local_talents.id"]),
        sa.ForeignKeyConstraint(
            ["search_run_id"],
            ["natural_language_search_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_hit_snapshots_tenant_id", _SNAPSHOTS_TABLE, ["tenant_id"])
    op.create_index("ix_search_hit_snapshots_search_run_id", _SNAPSHOTS_TABLE, ["search_run_id"])
    op.create_index(
        "ix_search_hit_snapshots_local_talent_id", _SNAPSHOTS_TABLE, ["local_talent_id"]
    )
    op.create_index(
        "ix_search_hit_snapshots_run_position",
        _SNAPSHOTS_TABLE,
        ["search_run_id", "sort_position"],
    )


def _extend_llm_call_records() -> None:
    op.add_column("llm_call_records", sa.Column("search_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_llm_call_records_search_run",
        "llm_call_records",
        _RUNS_TABLE,
        ["search_run_id"],
        ["id"],
    )
    op.drop_constraint("ck_llm_call_records_type", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_type",
        "llm_call_records",
        "call_type IN ('config_probe', 'job_requirement_parsing', 'search_interpretation')",
    )
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        _SCOPE_KEY_CHECK,
    )


def upgrade() -> None:
    _create_runs_table()
    _create_snapshots_table()
    _enable_tenant_rls(_RUNS_TABLE)
    _enable_tenant_rls(_SNAPSHOTS_TABLE)
    op.execute(f"REVOKE DELETE ON TABLE {_RUNS_TABLE} FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {_RUNS_TABLE} TO {_APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON TABLE {_SNAPSHOTS_TABLE} FROM {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {_SNAPSHOTS_TABLE} TO {_APP_ROLE}")
    _extend_llm_call_records()


def downgrade() -> None:
    op.drop_constraint("ck_llm_call_records_scope_key", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_scope_key",
        "llm_call_records",
        " ".join(  # noqa: FLY002
            (
                "(scope = 'platform' AND tenant_id IS NULL AND call_type = 'config_probe'",
                "AND platform_attempt_id IS NOT NULL AND job_requirement_parsing_task_id IS NULL",
                "AND configuration_version_id IS NULL AND input_snapshot_id IS NULL) OR",
                "(scope = 'tenant' AND tenant_id IS NOT NULL",
                "AND call_type = 'job_requirement_parsing' AND platform_attempt_id IS NULL",
                "AND job_requirement_parsing_task_id IS NOT NULL",
                "AND configuration_version_id IS NOT NULL AND input_snapshot_id IS NOT NULL)",
            )
        ),
    )
    op.drop_constraint("ck_llm_call_records_type", "llm_call_records", type_="check")
    op.create_check_constraint(
        "ck_llm_call_records_type",
        "llm_call_records",
        "call_type IN ('config_probe', 'job_requirement_parsing')",
    )
    op.drop_constraint("fk_llm_call_records_search_run", "llm_call_records", type_="foreignkey")
    op.drop_column("llm_call_records", "search_run_id")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SNAPSHOTS_TABLE}")
    op.drop_table(_SNAPSHOTS_TABLE)
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_RUNS_TABLE}")
    op.drop_table(_RUNS_TABLE)
