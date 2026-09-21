"""`integration_job`: the durable instruction, and the grant that confines who may change it.

Revision ID: 0022_integration_job
Revises: 0021_integrations_principal

**This is the record that lets the command message stay opaque** (spec §21.6.5, `FR-INTEG-014`).
RagCore writes the capability, its version and its parameters here in the same transaction as the
state change; the Service Bus message carries only `jobId`, `correlationId` and `kind`. The
Integrations Service reads its instruction from this row and **never from the message**.

```text
The message causes work to happen.
The durable job record provides the instruction, the authority and the tenant context.
```

**THE COLUMN-SCOPED GRANT IS THE SECURITY CONTROL IN THIS FILE**, and it is the reason the table is
in `platform` rather than in `integration`. The Integrations Service may write the four `result_*`
columns and nothing else. It MUST NOT be able to alter `catalogue_id`, `catalogue_version`,
`parameters` or `tenant_id` — a service that could rewrite its own instruction could execute an
operation other than the one governance authorized, which is a hard failure
(`.claude/rules/80-security-ops.md` §80.3).

**Why a grant rather than a trigger or application code.** Application code is one refactor from not
running. A trigger would work but states the rule as a procedure somebody can disable; a grant states
it as a right that was never held. `tests/security/` asserts the refusal comes from PostgreSQL.

**The four result columns are those named in `data-model.md` §Integration job.** ADR-0007 recorded
the exact set as unresolved; this revision settles it, and the record should be updated to say so.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_integration_job"
down_revision: str | None = "0021_integrations_principal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
TABLE = "integration_job"
RAGCORE = "synthia_ragcore"
INTEGRATIONS = "synthia_integrations"

# THE ENTIRE WRITABLE SURFACE for the Integrations principal. Adding a column here widens what an
# executing service may change about its own instruction, so the list is short, explicit, and the
# thing to argue about in review.
RESULT_COLUMNS: tuple[str, ...] = (
    "result_status",
    "result_verification",
    "result_execution_id",
    "result_recorded_at",
)

CREATE_STATUS = """\
CREATE TYPE platform.integration_job_status AS ENUM
    ('created', 'dispatched', 'completed', 'failed', 'expired')"""

CREATE_RESULT_STATUS = """\
CREATE TYPE platform.integration_result_status AS ENUM ('executed', 'failed')"""

CREATE_TABLE = """\
CREATE TABLE platform.integration_job (
    job_id UUID NOT NULL,
    work_item_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    catalogue_id VARCHAR(128) NOT NULL,
    catalogue_version INTEGER NOT NULL,
    parameters JSONB NOT NULL,
    status platform.integration_job_status DEFAULT 'created' NOT NULL,

    result_status platform.integration_result_status,
    result_verification platform.verification_outcome,
    result_execution_id UUID,
    result_recorded_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by VARCHAR(256),
    updated_by VARCHAR(256),
    version INTEGER DEFAULT 1 NOT NULL,

    CONSTRAINT pk_integration_job PRIMARY KEY (job_id),
    CONSTRAINT fk_integration_job_work_item_id
        FOREIGN KEY (work_item_id) REFERENCES platform.work_item (work_item_id) ON DELETE CASCADE,
    CONSTRAINT ck_integration_job_version_starts_at_one CHECK (catalogue_version >= 1),
    -- A result is recorded whole or not at all. A status without a timestamp, or a timestamp
    -- without a status, is a half-written result that a reader cannot interpret - and the reader
    -- here decides whether a user is told their issue is resolved.
    CONSTRAINT ck_integration_job_result_is_whole CHECK (
        (result_status IS NULL AND result_recorded_at IS NULL)
        OR (result_status IS NOT NULL AND result_recorded_at IS NOT NULL)
    )
)"""

CREATE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_integration_job_work_item_id ON platform.integration_job (work_item_id)",
    "CREATE INDEX ix_integration_job_tenant_id ON platform.integration_job (tenant_id)",
    # Partial: the sweeper looks only for work that is still in flight, and an index over completed
    # rows would grow without bound while answering a question nobody asks.
    "CREATE INDEX ix_integration_job_in_flight ON platform.integration_job (expires_at) "
    "WHERE status IN ('created', 'dispatched')",
)


def upgrade() -> None:
    """Create the table, its indexes, and the two disjoint grants."""
    op.execute(CREATE_STATUS)
    op.execute(CREATE_RESULT_STATUS)
    op.execute(CREATE_TABLE)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    # RagCore OWNS the instruction. It writes the row, dispatches it, and reads the result back.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {SCHEMA}.{TABLE} TO {RAGCORE}")  # noqa: S608

    # THE INTEGRATIONS PRINCIPAL: SELECT on the row, UPDATE on FOUR COLUMNS, and nothing else.
    #
    # PostgreSQL column-level privileges are the mechanism: `GRANT UPDATE (a, b) ON t` permits an
    # UPDATE that touches only those columns and refuses one that touches any other - refused by the
    # database, with a permission error, before the statement runs.
    #
    # Note there is NO INSERT and NO DELETE. The Integrations Service cannot create an instruction
    # for itself, and cannot remove the evidence of one it was given.
    op.execute(f"GRANT SELECT ON {SCHEMA}.{TABLE} TO {INTEGRATIONS}")  # noqa: S608
    columns = ", ".join(RESULT_COLUMNS)
    op.execute(f"GRANT UPDATE ({columns}) ON {SCHEMA}.{TABLE} TO {INTEGRATIONS}")  # noqa: S608


def downgrade() -> None:
    """Revoke, then drop."""
    op.execute(f"REVOKE ALL ON {SCHEMA}.{TABLE} FROM {INTEGRATIONS}")  # noqa: S608
    op.execute(f"REVOKE ALL ON {SCHEMA}.{TABLE} FROM {RAGCORE}")  # noqa: S608
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{TABLE}")
    op.execute("DROP TYPE IF EXISTS platform.integration_result_status")
    op.execute("DROP TYPE IF EXISTS platform.integration_job_status")
