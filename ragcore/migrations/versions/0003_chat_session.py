"""chat_session: nine states, and a retention clock that starts at the terminal one.

Revision ID: 0003_chat_session
Revises: 0002_tenant_mapping

``content_expires_at`` is nullable and stays null while the session is active
(spec FR-SESS-020). The partial index over it is the retention sweeper's only query.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_chat_session"
down_revision: str | None = "0002_tenant_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "chat_session"

CREATE_TABLE = """\
CREATE TABLE platform.chat_session (
    session_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    requester_oid UUID NOT NULL,
    state platform.session_state NOT NULL,
    case_reference VARCHAR(128),
    closed_at TIMESTAMP WITH TIME ZONE,
    content_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_chat_session PRIMARY KEY (session_id),
    CONSTRAINT fk_chat_session_tenant_id FOREIGN KEY(tenant_id) REFERENCES platform.tenant_mapping (tenant_id)
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_chat_session_content_expires_at ON platform.chat_session (content_expires_at) WHERE content_expires_at IS NOT NULL",
    "CREATE INDEX ix_chat_session_tenant_id_requester_oid_created_at ON platform.chat_session (tenant_id, requester_oid, created_at DESC)",
    "CREATE INDEX ix_chat_session_tenant_id_state ON platform.chat_session (tenant_id, state)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
