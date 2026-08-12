"""Editable requirement documents, optimistic revisions, and replacement binding.

Revision ID: 0013_requirement_draft_editing
Revises: 0012_requirement_draft
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from relationship_network_api.job_requirement_validation import (
    build_editable_requirement_document,
    validate_editable_requirement_document,
)
from relationship_network_api.llm_assets import manifest

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0013_requirement_draft_editing"
down_revision: str | None = "0012_requirement_draft"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_editor_asset_columns() -> None:
    op.add_column(
        "job_requirement_schema_versions",
        sa.Column("editor_schema_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "job_requirement_schema_versions",
        sa.Column("editor_asset_path", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "job_requirement_schema_versions",
        sa.Column("editor_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "job_requirement_schema_versions",
        sa.Column(
            "editor_schema_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_requirement_schema_versions_editor_schema_id",
        "job_requirement_schema_versions",
        ["editor_schema_id"],
    )
    op.create_unique_constraint(
        "uq_requirement_schema_versions_editor_asset_path",
        "job_requirement_schema_versions",
        ["editor_asset_path"],
    )
    op.create_unique_constraint(
        "uq_requirement_schema_versions_editor_sha256",
        "job_requirement_schema_versions",
        ["editor_sha256"],
    )
    op.create_check_constraint(
        "ck_requirement_schema_versions_editor_asset",
        "job_requirement_schema_versions",
        "(editor_schema_id IS NULL AND editor_asset_path IS NULL "
        "AND editor_sha256 IS NULL AND editor_schema_json IS NULL) OR "
        "(editor_schema_id IS NOT NULL AND editor_asset_path IS NOT NULL "
        "AND editor_sha256 IS NOT NULL AND editor_schema_json IS NOT NULL)",
    )
    asset = manifest.JOB_REQUIREMENT_SCHEMA_V2
    if (
        asset.editor_package is None
        or asset.editor_path is None
        or asset.editor_sha256 is None
        or asset.editor_schema_id is None
    ):
        message = "v2 editor Schema asset is incomplete"
        raise RuntimeError(message)
    manifest.validate_deployed_assets()
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "DISABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE job_requirement_schema_versions SET "
            "editor_schema_id = :schema_id, editor_asset_path = :asset_path, "
            "editor_sha256 = :sha256, editor_schema_json = CAST(:schema_json AS jsonb) "
            "WHERE id = :id"
        ),
        {
            "asset_path": f"{asset.editor_package}/{asset.editor_path}",
            "id": asset.id,
            "schema_id": asset.editor_schema_id,
            "schema_json": json.dumps(
                manifest.read_requirement_editor_schema(asset.id),
                ensure_ascii=False,
            ),
            "sha256": asset.editor_sha256,
        },
    )
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "ENABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )


def _extend_drafts_and_tasks() -> None:
    op.add_column(
        "job_requirement_drafts",
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "job_requirement_drafts",
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_requirement_drafts_updated_by",
        "job_requirement_drafts",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE job_requirement_drafts SET updated_by = created_by, status_changed_at = created_at"
    )
    op.alter_column("job_requirement_drafts", "status_changed_at", nullable=False)
    op.create_unique_constraint(
        "uq_requirement_drafts_id_tenant_job",
        "job_requirement_drafts",
        ["id", "tenant_id", "job_id"],
    )
    op.add_column(
        "job_requirement_parsing_tasks",
        sa.Column("replaces_draft_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "job_requirement_parsing_tasks",
        sa.Column("replaces_draft_revision", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_requirement_tasks_replaced_draft",
        "job_requirement_parsing_tasks",
        "((replaces_draft_id IS NULL) = (replaces_draft_revision IS NULL)) "
        "AND (replaces_draft_revision IS NULL OR replaces_draft_revision > 0)",
    )
    op.create_foreign_key(
        "fk_requirement_tasks_replaced_draft_tenant_job",
        "job_requirement_parsing_tasks",
        "job_requirement_drafts",
        ["replaces_draft_id", "tenant_id", "job_id"],
        ["id", "tenant_id", "job_id"],
    )


def _backfill_editable_documents() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, requirement_schema_version_id, result_json "
            "FROM job_requirement_drafts ORDER BY id"
        )
    ).mappings()
    asset = manifest.JOB_REQUIREMENT_SCHEMA_V2
    editor_schema = manifest.read_requirement_editor_schema(asset.id)
    for row in rows:
        if row["requirement_schema_version_id"] != asset.id:
            message = "0013 cannot backfill a draft without an editor Schema asset"
            raise RuntimeError(message)
        document = build_editable_requirement_document(
            cast("dict[str, object]", row["result_json"]),
            draft_id=row["id"],
        )
        validated = validate_editable_requirement_document(
            document,
            schema=editor_schema,
            asset=asset,
        )
        connection.execute(
            sa.text(
                "UPDATE job_requirement_drafts "
                "SET result_json = CAST(:result_json AS jsonb) WHERE id = :id"
            ),
            {
                "id": row["id"],
                "result_json": json.dumps(validated, ensure_ascii=False),
            },
        )


def upgrade() -> None:
    _add_editor_asset_columns()
    _extend_drafts_and_tasks()
    _backfill_editable_documents()


def _restore_model_output(document: dict[str, object]) -> dict[str, object]:
    restored: dict[str, list[object]] = {
        "hard_conditions": [],
        "preference_conditions": [],
        "unsupported_conditions": [],
    }
    for key in ("hard_conditions", "preference_conditions", "unsupported_conditions"):
        for item in cast("list[dict[str, object]]", document[key]):
            if item["origin"] == "model" and item["model_snapshot"] is not None:
                restored[key].append(deepcopy(item["model_snapshot"]))
    for fact in cast("list[dict[str, object]]", document["removed_facts"]):
        snapshot = fact["model_snapshot"]
        if fact["origin"] != "model" or snapshot is None:
            continue
        kind = cast("str", fact["kind"])
        target = {
            "hard_condition": "hard_conditions",
            "preference_condition": "preference_conditions",
            "unsupported_condition": "unsupported_conditions",
        }[kind]
        restored[target].append(deepcopy(snapshot))
    conflicts = [
        deepcopy(item["model_snapshot"])
        for item in cast("list[dict[str, object]]", document["source_conflicts"])
    ]
    query = cast("dict[str, object]", document["research_topic_query"])
    return {
        "hard_conditions": restored["hard_conditions"],
        "preference_conditions": restored["preference_conditions"],
        "research_topic_query": query["model_value"],
        "unsupported_conditions": restored["unsupported_conditions"],
        "source_conflicts": conflicts,
    }


def _downgrade_documents() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, result_json FROM job_requirement_drafts ORDER BY id")
    ).mappings()
    for row in rows:
        restored = _restore_model_output(cast("dict[str, object]", row["result_json"]))
        connection.execute(
            sa.text(
                "UPDATE job_requirement_drafts "
                "SET result_json = CAST(:result_json AS jsonb) WHERE id = :id"
            ),
            {
                "id": row["id"],
                "result_json": json.dumps(restored, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    _downgrade_documents()
    op.drop_constraint(
        "fk_requirement_tasks_replaced_draft_tenant_job",
        "job_requirement_parsing_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_requirement_tasks_replaced_draft",
        "job_requirement_parsing_tasks",
        type_="check",
    )
    op.drop_column("job_requirement_parsing_tasks", "replaces_draft_revision")
    op.drop_column("job_requirement_parsing_tasks", "replaces_draft_id")
    op.drop_constraint(
        "uq_requirement_drafts_id_tenant_job",
        "job_requirement_drafts",
        type_="unique",
    )
    op.drop_constraint(
        "fk_requirement_drafts_updated_by",
        "job_requirement_drafts",
        type_="foreignkey",
    )
    op.drop_column("job_requirement_drafts", "status_changed_at")
    op.drop_column("job_requirement_drafts", "updated_by")
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "DISABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )
    op.execute(
        "UPDATE job_requirement_schema_versions SET editor_schema_id = NULL, "
        "editor_asset_path = NULL, editor_sha256 = NULL, editor_schema_json = NULL"
    )
    op.execute(
        "ALTER TABLE job_requirement_schema_versions "
        "ENABLE TRIGGER trg_job_requirement_schema_versions_immutable"
    )
    op.drop_constraint(
        "ck_requirement_schema_versions_editor_asset",
        "job_requirement_schema_versions",
        type_="check",
    )
    op.drop_constraint(
        "uq_requirement_schema_versions_editor_sha256",
        "job_requirement_schema_versions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_requirement_schema_versions_editor_asset_path",
        "job_requirement_schema_versions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_requirement_schema_versions_editor_schema_id",
        "job_requirement_schema_versions",
        type_="unique",
    )
    op.drop_column("job_requirement_schema_versions", "editor_schema_json")
    op.drop_column("job_requirement_schema_versions", "editor_sha256")
    op.drop_column("job_requirement_schema_versions", "editor_asset_path")
    op.drop_column("job_requirement_schema_versions", "editor_schema_id")
