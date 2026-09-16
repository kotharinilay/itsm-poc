"""ingestion_run: the derived index's rebuild record.

Revision ID: 0016_ingestion_run
Revises: 0015_idempotency_record

The retrieval index is derived, so a lost index is rebuilt by re-running ingestion from a
watermark rather than restored — which is why this table records a watermark and no
document body. Ingestion never writes authority.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_ingestion_run"
down_revision: str | None = "0015_idempotency_record"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "ingestion_run"

CREATE_TABLE = """\
CREATE TABLE platform.ingestion_run (
    run_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    source VARCHAR(256) NOT NULL,
    watermark VARCHAR(512),
    document_count INTEGER DEFAULT 0 NOT NULL,
    state platform.ingestion_run_state NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_ingestion_run PRIMARY KEY (run_id),
    CONSTRAINT fk_ingestion_run_tenant_id FOREIGN KEY(tenant_id) REFERENCES platform.tenant_mapping (tenant_id) ON DELETE CASCADE
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_ingestion_run_tenant_id_source_started_at ON platform.ingestion_run (tenant_id, source, started_at DESC)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
