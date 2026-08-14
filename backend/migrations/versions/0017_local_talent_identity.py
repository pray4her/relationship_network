"""Local talent master identity, external identifier mapping, and identity events.

Establishes the third RLS posture (ADR 0026): three global tables with no
``tenant_id`` that every authenticated app role may read but only the sync role
may write.

Revision ID: 0017_local_talent_identity
Revises: 0016_schema_history_retention
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_local_talent_identity"
down_revision: str | None = "0016_schema_history_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "relationship_app"
_SYNC_ROLE = "relationship_talent_sync"
_LOCAL_TALENTS_TABLE = "local_talents"
_EXTERNAL_IDS_TABLE = "talent_external_ids"
_EVENTS_TABLE = "talent_identity_events"
_TALENT_TABLES = (_LOCAL_TALENTS_TABLE, _EXTERNAL_IDS_TABLE, _EVENTS_TABLE)


def _create_role(role: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN; "
        "END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT {role} TO CURRENT_USER")


def _create_tables() -> None:
    op.create_table(
        _LOCAL_TALENTS_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
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
            "availability",
            sa.String(length=30),
            server_default=sa.text("'available'"),
            nullable=False,
        ),
        sa.Column(
            "last_synced_at",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "availability IN ('available', 'temporarily_unavailable')",
            name="ck_local_talents_availability",
        ),
        sa.CheckConstraint(
            "chinese_identity IN ('国内华人', '海外华人', '外国人')",
            name="ck_local_talents_chinese_identity",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        _EXTERNAL_IDS_TABLE,
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("local_talent_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('canonical_person_id', 'source_id')",
            name="ck_talent_external_ids_kind",
        ),
        sa.ForeignKeyConstraint(
            ["local_talent_id"],
            ["local_talents.id"],
            name="fk_talent_external_ids_local_talent",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("external_id"),
    )
    op.create_index(
        "ix_talent_external_ids_local_talent_id",
        _EXTERNAL_IDS_TABLE,
        ["local_talent_id"],
    )

    op.create_table(
        _EVENTS_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("local_talent_id", sa.Uuid(), nullable=False),
        sa.Column("data_version", sa.String(length=100), nullable=False),
        sa.Column("external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("merged_from_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'merged', 'marked_unavailable', 'marked_available')",
            name="ck_talent_identity_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["local_talent_id"],
            ["local_talents.id"],
            name="fk_talent_identity_events_local_talent",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_talent_identity_events_local_talent_id",
        _EVENTS_TABLE,
        ["local_talent_id"],
    )


def _enable_rls_and_grants() -> None:
    """App role: SELECT only on the shared master. Sync role: sole writer."""
    for table in _TALENT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_app_select ON {table} FOR SELECT TO {_APP_ROLE} USING (true)"
        )
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {_APP_ROLE}")
        op.execute(f"GRANT SELECT ON TABLE {table} TO {_APP_ROLE}")

    for table in (_LOCAL_TALENTS_TABLE, _EXTERNAL_IDS_TABLE):
        op.execute(
            f"CREATE POLICY {table}_sync_all ON {table} "
            f"TO {_SYNC_ROLE} USING (true) WITH CHECK (true)"
        )
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {_SYNC_ROLE}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {_SYNC_ROLE}")

    op.execute(
        f"CREATE POLICY {_EVENTS_TABLE}_sync_insert ON {_EVENTS_TABLE} "
        f"FOR INSERT TO {_SYNC_ROLE} WITH CHECK (true)"
    )
    op.execute(f"REVOKE ALL ON TABLE {_EVENTS_TABLE} FROM {_SYNC_ROLE}")
    op.execute(f"GRANT INSERT ON TABLE {_EVENTS_TABLE} TO {_SYNC_ROLE}")


def upgrade() -> None:
    _create_role(_SYNC_ROLE)
    _create_tables()
    _enable_rls_and_grants()


def downgrade() -> None:
    for table in _TALENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_app_select ON {table}")
    op.execute(f"DROP POLICY IF EXISTS {_LOCAL_TALENTS_TABLE}_sync_all ON {_LOCAL_TALENTS_TABLE}")
    op.execute(f"DROP POLICY IF EXISTS {_EXTERNAL_IDS_TABLE}_sync_all ON {_EXTERNAL_IDS_TABLE}")
    op.execute(f"DROP POLICY IF EXISTS {_EVENTS_TABLE}_sync_insert ON {_EVENTS_TABLE}")
    for table in _TALENT_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table(_EVENTS_TABLE)
    op.drop_table(_EXTERNAL_IDS_TABLE)
    op.drop_table(_LOCAL_TALENTS_TABLE)
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_SYNC_ROLE}")
    op.execute(f"REVOKE {_SYNC_ROLE} FROM CURRENT_USER")
    op.execute(f"DROP ROLE IF EXISTS {_SYNC_ROLE}")
