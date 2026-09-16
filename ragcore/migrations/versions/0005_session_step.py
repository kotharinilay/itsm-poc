"""session_step: the progress trail behind vw_session_step_v1.

Revision ID: 0005_session_step
Revises: 0004_message

Published by the read contract and absent from data-model.md. Created here rather than
leaving a published view with nothing underneath it. Carries no authority field.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_session_step"
down_revision: str | None = "0004_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "session_step"

CREATE_TABLE = """\
CREATE TABLE platform.session_step (
    step_id UUID NOT NULL,
    session_id UUID NOT NULL,
    kind VARCHAR(64) NOT NULL,
    summary VARCHAR(512) NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_session_step PRIMARY KEY (step_id),
    CONSTRAINT fk_session_step_session_id FOREIGN KEY(session_id) REFERENCES platform.chat_session (session_id) ON DELETE CASCADE
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_session_step_tenant_id_session_id_created_at ON platform.session_step (tenant_id, session_id, created_at)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
