"""tenant_entitlement: least privilege, per organisation.

Revision ID: 0009_tenant_entitlement
Revises: 0008_governance_record

``credential_reference`` holds a Key Vault reference and **never a secret value**
(spec FR-EXT-016). This table is deliberately not published by any view, because a view
over it would be one SELECT * away from publishing that column.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_tenant_entitlement"
down_revision: str | None = "0008_governance_record"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "tenant_entitlement"

CREATE_TABLE = """\
CREATE TABLE platform.tenant_entitlement (
    tenant_id UUID NOT NULL,
    catalogue_id VARCHAR(128) NOT NULL,
    enabled BOOLEAN DEFAULT false NOT NULL,
    credential_reference VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_tenant_entitlement PRIMARY KEY (tenant_id, catalogue_id),
    CONSTRAINT fk_tenant_entitlement_tenant_id FOREIGN KEY(tenant_id) REFERENCES platform.tenant_mapping (tenant_id) ON DELETE CASCADE
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_tenant_entitlement_tenant_id_catalogue_id ON platform.tenant_entitlement (tenant_id, catalogue_id) WHERE enabled",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
