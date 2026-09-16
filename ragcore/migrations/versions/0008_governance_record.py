"""governance_record: the catalogue, keyed by id and version.

Revision ID: 0008_governance_record
Revises: 0007_work_item

The CHECK on ``requires_elevation`` is what makes 'Alpha permits no elevation' (ADR-0004)
a property of the store rather than of whatever loads it. A catalogue entry is never
edited in place; a change is a new version row, so an approval keeps meaning what it meant.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_governance_record"
down_revision: str | None = "0007_work_item"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "governance_record"

CREATE_TABLE = """\
CREATE TABLE platform.governance_record (
    catalogue_id VARCHAR(128) NOT NULL,
    version INTEGER NOT NULL,
    kind platform.capability_kind NOT NULL,
    default_treatment platform.execution_treatment NOT NULL,
    accepted_roles TEXT[] NOT NULL,
    is_reference_fixture BOOLEAN NOT NULL,
    requires_elevation BOOLEAN NOT NULL,
    risk_tier platform.risk_tier NOT NULL,
    commands JSONB,
    content_hash VARCHAR(128),
    verification_tool VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    CONSTRAINT pk_governance_record PRIMARY KEY (catalogue_id, version),
    CONSTRAINT ck_governance_record_alpha_permits_no_elevation CHECK (requires_elevation = false),
    CONSTRAINT ck_governance_record_catalogue_versions_start_at_one CHECK (version >= 1)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_governance_record_is_reference_fixture ON platform.governance_record (is_reference_fixture)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
