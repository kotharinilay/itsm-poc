"""tenant_mapping: the registry, and the only accepted external key.

Revision ID: 0002_tenant_mapping
Revises: 0001_platform_schema

``entra_tid`` is unique because two platform tenants claiming one Entra tenant would make
admission ambiguous in the direction that leaks data. It is created first because every
other tenant-scoped table references it.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_tenant_mapping"
down_revision: str | None = "0001_platform_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "tenant_mapping"

CREATE_TABLE = """\
CREATE TABLE platform.tenant_mapping (
    tenant_id UUID NOT NULL,
    entra_tid UUID NOT NULL,
    display_name VARCHAR(256) NOT NULL,
    status platform.tenant_status NOT NULL,
    retention_overrides JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_tenant_mapping PRIMARY KEY (tenant_id),
    CONSTRAINT uq_tenant_mapping_entra_tid UNIQUE (entra_tid)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_tenant_mapping_status ON platform.tenant_mapping (status)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
