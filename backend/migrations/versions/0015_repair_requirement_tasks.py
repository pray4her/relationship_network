"""Repair incomplete job_requirement_parsing_tasks columns and transition trigger.

Revision ID: 0015_repair_requirement_tasks
Revises: 0014_requirement_versions

Some environments applied an incomplete early shape of 0012 while alembic_version
advanced. This repair is idempotent: fresh databases that already match the model
are no-ops aside from replacing the transition trigger with the full definition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0015_repair_requirement_tasks"
down_revision: str | None = "0014_requirement_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "job_requirement_parsing_tasks"


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(_TABLE)}


def _index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(_TABLE) if index["name"]}


def _unique_constraint_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(_TABLE)
        if constraint["name"]
    }


def _check_constraint_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(_TABLE)
        if constraint["name"]
    }


def _add_missing_columns() -> None:
    existing = _column_names()
    if "idempotency_key" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )
        op.execute(
            sa.text(
                """
                UPDATE job_requirement_parsing_tasks
                SET idempotency_key = 'legacy-repair:' || id::text
                WHERE idempotency_key IS NULL
                """
            )
        )
        op.alter_column(_TABLE, "idempotency_key", nullable=False)
    if "effective_request_sha256" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("effective_request_sha256", sa.String(length=64), nullable=True),
        )
        op.execute(
            sa.text(
                """
                UPDATE job_requirement_parsing_tasks
                SET effective_request_sha256 = repeat('0', 64)
                WHERE effective_request_sha256 IS NULL
                """
            )
        )
        op.alter_column(_TABLE, "effective_request_sha256", nullable=False)
    if "structured_invalid_count" not in existing:
        op.add_column(
            _TABLE,
            sa.Column(
                "structured_invalid_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            ),
        )
    if "lease_token" not in existing:
        op.add_column(_TABLE, sa.Column("lease_token", sa.Uuid(), nullable=True))
    if "lease_expires_at" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "last_heartbeat_at" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "next_attempt_at" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "updated_at" not in existing:
        op.add_column(
            _TABLE,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def _add_missing_constraints_and_indexes() -> None:
    checks = _check_constraint_names()
    uniques = _unique_constraint_names()
    indexes = _index_names()

    if "ck_requirement_tasks_structured_invalid_budget" not in checks:
        op.create_check_constraint(
            "ck_requirement_tasks_structured_invalid_budget",
            _TABLE,
            "structured_invalid_count BETWEEN 0 AND 2",
        )
    if "ck_requirement_tasks_lease_fields" not in checks:
        op.create_check_constraint(
            "ck_requirement_tasks_lease_fields",
            _TABLE,
            """
            ((status IN ('running', 'cancel_requested')) =
             (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL
              AND last_heartbeat_at IS NOT NULL))
            """,
        )
    if "ck_requirement_tasks_retry_fields" not in checks:
        op.create_check_constraint(
            "ck_requirement_tasks_retry_fields",
            _TABLE,
            "((status = 'retry_scheduled') = (next_attempt_at IS NOT NULL))",
        )
    if "ck_requirement_tasks_completion_fields" not in checks:
        op.create_check_constraint(
            "ck_requirement_tasks_completion_fields",
            _TABLE,
            "((status IN ('succeeded', 'failed', 'cancelled')) = (completed_at IS NOT NULL))",
        )
    if "uq_requirement_tasks_tenant_idempotency" not in uniques:
        op.create_unique_constraint(
            "uq_requirement_tasks_tenant_idempotency",
            _TABLE,
            ["tenant_id", "idempotency_key"],
        )
    if "ix_requirement_tasks_retry_due" not in indexes:
        op.create_index(
            "ix_requirement_tasks_retry_due",
            _TABLE,
            ["next_attempt_at"],
            postgresql_where=sa.text("status = 'retry_scheduled'"),
        )
    if "ix_requirement_tasks_lease_due" not in indexes:
        op.create_index(
            "ix_requirement_tasks_lease_due",
            _TABLE,
            ["lease_expires_at"],
            postgresql_where=sa.text("status IN ('running', 'cancel_requested')"),
        )


def _replace_transition_trigger() -> None:
    """Install the full lease/retry-aware transition guard from 0012."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_requirement_task_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.tenant_id <> OLD.tenant_id OR NEW.job_id <> OLD.job_id
             OR NEW.input_snapshot_id <> OLD.input_snapshot_id
             OR NEW.configuration_version_id <> OLD.configuration_version_id
             OR NEW.idempotency_key <> OLD.idempotency_key
             OR NEW.effective_request_sha256 <> OLD.effective_request_sha256
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'immutable requirement task fields cannot be changed';
          END IF;
          IF OLD.status IN ('succeeded', 'failed', 'cancelled') THEN
            RAISE EXCEPTION 'terminal requirement task cannot be changed';
          END IF;
          IF NEW.status <> OLD.status AND NOT (
               (OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled'))
            OR (OLD.status = 'running' AND NEW.status IN (
                  'retry_scheduled', 'succeeded', 'failed', 'cancel_requested'))
            OR (OLD.status = 'running' AND NEW.status = 'queued'
                AND OLD.lease_expires_at <= now())
            OR (OLD.status = 'retry_scheduled' AND NEW.status IN ('queued', 'cancelled'))
            OR (OLD.status = 'cancel_requested' AND NEW.status = 'cancelled')
          ) THEN
            RAISE EXCEPTION 'illegal requirement task transition: % -> %',
              OLD.status, NEW.status;
          END IF;
          IF OLD.status IN ('running', 'cancel_requested')
             AND NEW.status IN ('running', 'cancel_requested')
             AND NEW.lease_token IS DISTINCT FROM OLD.lease_token THEN
            RAISE EXCEPTION 'requirement task lease token cannot be replaced';
          END IF;
          IF NEW.status IN ('running', 'cancel_requested') AND (
               NEW.lease_token IS NULL
            OR NEW.lease_expires_at IS NULL
            OR NEW.last_heartbeat_at IS NULL
          ) THEN
            RAISE EXCEPTION 'running requirement task requires a complete lease';
          END IF;
          IF NEW.status NOT IN ('running', 'cancel_requested') AND (
               NEW.lease_token IS NOT NULL
            OR NEW.lease_expires_at IS NOT NULL
            OR NEW.last_heartbeat_at IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'non-running requirement task cannot retain a lease';
          END IF;
          IF NEW.status = 'retry_scheduled' AND NEW.next_attempt_at IS NULL THEN
            RAISE EXCEPTION 'scheduled retry requires next_attempt_at';
          END IF;
          IF NEW.status <> 'retry_scheduled' AND NEW.next_attempt_at IS NOT NULL THEN
            RAISE EXCEPTION 'only scheduled retry may have next_attempt_at';
          END IF;
          IF NEW.status IN ('succeeded', 'failed', 'cancelled')
             AND NEW.completed_at IS NULL THEN
            RAISE EXCEPTION 'terminal requirement task requires completed_at';
          END IF;
          IF NEW.status NOT IN ('succeeded', 'failed', 'cancelled')
             AND NEW.completed_at IS NOT NULL THEN
            RAISE EXCEPTION 'nonterminal requirement task cannot have completed_at';
          END IF;
          IF NEW.status = 'failed' AND NEW.error_code IS NULL THEN
            RAISE EXCEPTION 'failed requirement task requires error_code';
          END IF;
          NEW.updated_at = now();
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_requirement_task_transition ON job_requirement_parsing_tasks"
    )
    op.execute(
        """
        CREATE TRIGGER trg_requirement_task_transition BEFORE UPDATE
        ON job_requirement_parsing_tasks FOR EACH ROW
        EXECUTE FUNCTION validate_requirement_task_transition()
        """
    )


def upgrade() -> None:
    _add_missing_columns()
    _add_missing_constraints_and_indexes()
    _replace_transition_trigger()


def downgrade() -> None:
    """Keep repaired columns; only drop objects uniquely introduced when absent before.

    Downgrade intentionally leaves columns in place. Removing them would break the
    application contract already required by 0012 and would destroy repair evidence
    on drifted databases. Replacing the trigger with a weaker guard is also unsafe.
    """
    # No-op by design: this revision only restores expected 0012 shape.
    return
