"""message: conversation turns, tenant-stamped on the row.

Revision ID: 0004_message
Revises: 0003_chat_session

``tenant_id`` is denormalised so the filter is local to the table rather than dependent on
a join a future query could change. ``ON DELETE CASCADE`` because retention and erasure
are both hard deletes and an orphaned message would defeat both.

The DDL below is a snapshot, written out in full rather than assembled from the models at run
time: a migration that imported the current models would apply whatever they say today, which is
the opposite of what a versioned revision is for.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_message"
down_revision: str | None = "0003_chat_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "message"

CREATE_TABLE = """\
CREATE TABLE platform.message (
    message_id UUID NOT NULL,
    session_id UUID NOT NULL,
    sender_kind platform.sender_kind NOT NULL,
    sender_oid UUID,
    body TEXT NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_message PRIMARY KEY (message_id),
    CONSTRAINT ck_message_agent_messages_carry_no_principal CHECK ((sender_kind = 'agent') = (sender_oid IS NULL)),
    CONSTRAINT fk_message_session_id FOREIGN KEY(session_id) REFERENCES platform.chat_session (session_id) ON DELETE CASCADE
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_message_tenant_id_session_id_created_at ON platform.message (tenant_id, session_id, created_at)",
)


def upgrade() -> None:
    """Create the table and its indexes."""
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop it. The indexes go with the table; the enum types belong to revision 0001."""
    op.execute(f"DROP TABLE {SCHEMA}.{TABLE}")
