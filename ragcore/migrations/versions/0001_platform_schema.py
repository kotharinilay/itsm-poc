"""platform schema and every enum type it declares.

Revision ID: 0001_platform_schema
Revises: None

**The first revision creates the schema Alembic owns and nothing else's.** ``langgraph`` is created
by ``ragcore.graph.checkpointer.provision_checkpoint_schema``, run from the same gated migration job
and never at application startup (research R-004, ADR-0003). Nothing here reaches into it.

*Amended 2026-09-19: this used to say the schema was created by the checkpointer's own ``setup()``.
It was not — ``setup()`` issues unqualified DDL into whatever ``search_path`` resolves to, so the
job failed with "no schema has been selected to create in" against any database where nobody had
created it. Provisioning now creates it, still outside Alembic, because the schema belongs to the
checkpointer and autogenerate deliberately cannot see inside it.*

**Every enum type is created once, here, and shared by every table that references it.** Two tables
declaring their own ``verification_outcome`` would be two PostgreSQL types with the same spelling:
a join across them would need a cast, and a cast loses the protection the type exists to give —
that a column cannot hold a value nobody defined.

The spellings are the *values* of the domain enums in :mod:`ragcore.domain`, not their Python
names. ``awaiting_user``, not ``AWAITING_USER``. That spelling is the specification's, the graph
state literals', the published views' and the monolith's converter's, and they all have to agree.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_platform_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"

ENUM_TYPES: tuple[str, ...] = (
    "tenant_status",
    "session_state",
    "sender_kind",
    "feedback_signal",
    "work_item_state",
    "approval_state",
    "approval_verdict",
    "consent_verdict",
    "operation_status",
    "execution_treatment",
    "verification_outcome",
    "execution_method",
    "capability_kind",
    "risk_tier",
    "ingestion_run_state",
)
"""Named separately from the DDL so the downgrade drops exactly what the upgrade created.

A type left behind by an incomplete downgrade makes the next upgrade fail with ``type already
exists`` — which is the failure ``test_up_down_consistency`` exists to catch, and it catches it
only if this list is complete.
"""

CREATE_TYPES: tuple[str, ...] = (
    "CREATE TYPE platform.tenant_status AS ENUM ('active', 'suspended', 'offboarded')",
    "CREATE TYPE platform.session_state AS ENUM ('conversational', 'resolving', 'awaiting_user', "
    "'awaiting_consent', 'awaiting_approval', 'staff_controlled', 'resolved', 'escalated', "
    "'closed_declined')",
    "CREATE TYPE platform.sender_kind AS ENUM ('end_user', 'agent', 'staff')",
    "CREATE TYPE platform.feedback_signal AS ENUM ('positive', 'negative')",
    "CREATE TYPE platform.work_item_state AS ENUM ('open', 'awaiting_decision', 'authorized', "
    "'claimed', 'executed', 'failed', 'expired', 'cancelled', 'escalated')",
    "CREATE TYPE platform.approval_state AS ENUM ('none', 'pending', 'approved', 'rejected', "
    "'expired')",
    "CREATE TYPE platform.approval_verdict AS ENUM ('approved', 'rejected')",
    "CREATE TYPE platform.consent_verdict AS ENUM ('granted', 'refused')",
    "CREATE TYPE platform.operation_status AS ENUM ('proposed', 'gated', 'authorized', 'executed', "
    "'failed', 'refused')",
    "CREATE TYPE platform.execution_treatment AS ENUM ('AUTO', 'END_USER_APPROVAL', "
    "'STAFF_APPROVAL', 'NOT_ALLOWED')",
    "CREATE TYPE platform.verification_outcome AS ENUM ('server_confirmed', 'client_attested', "
    "'contradicted')",
    "CREATE TYPE platform.execution_method AS ENUM ('workload', 'desktop_script', 'none')",
    "CREATE TYPE platform.capability_kind AS ENUM ('read', 'action')",
    "CREATE TYPE platform.risk_tier AS ENUM ('informational', 'low_impact')",
    "CREATE TYPE platform.ingestion_run_state AS ENUM ('running', 'completed', 'failed')",
)


def upgrade() -> None:
    """Create the schema, then every type the tables that follow will reference."""
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    for statement in CREATE_TYPES:
        op.execute(statement)


def downgrade() -> None:
    """Drop every type. **The schema itself stays.**

    ``alembic_version`` lives in this schema (``alembic.ini``), so dropping it here would delete
    the table Alembic is about to write this very downgrade into. The schema is Alembic's own
    container, not application state, and leaving an empty one behind is the honest outcome: the
    next upgrade finds it, ``CREATE SCHEMA IF NOT EXISTS`` is a no-op, and nothing is lost.

    Each ``DROP TYPE`` is unqualified by ``IF EXISTS`` on purpose. By the time this runs every
    table revision has already downgraded, so a type that is missing means a revision failed to
    create it — and a loud error is better than a downgrade that reports success.
    """
    for type_name in reversed(ENUM_TYPES):
        op.execute(f"DROP TYPE {SCHEMA}.{type_name}")
