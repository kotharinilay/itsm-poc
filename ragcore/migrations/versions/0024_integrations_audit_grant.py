"""Grant the Integrations principal INSERT on audit_event. **Insert only, and not SELECT.**

`FR-INTEG-024`, T326, analysis finding X8.

**Audit does not fork.** The specification requires one audit store, with the actor chain recording
the Integrations principal as the **executing** principal. Until this revision the principal held no
grant on ``platform.audit_event`` at all, so that requirement had no path to satisfy: the service
could execute an authorized capability and record an execution record in its own schema, but nothing
it did reached the platform's durable audit. The gap was a missing grant that no task named.

**INSERT, and deliberately not SELECT** — which is narrower than RagCore's own grant on this table
(revision 0019 gives RagCore ``SELECT, INSERT``). Two reasons, and they are different:

* Reading the audit store would let this service see records belonging to **other actors and other
  organisations**. It has no question that requires reading audit, and the table carries no tenant
  predicate of its own, so the only thing restricting it would be a query nobody reviews.
* It is the deployable with an egress path to every customer system. Read access to the platform's
  full audit history is the sort of capability whose blast radius is worst exactly here.

**No UPDATE and no DELETE**, matching the append-only rule this table has carried since revision
0013. Those are the two statements that could rewrite history, and no principal holds them.

**This revision creates no object.** It is a grant and nothing else, so ``autogenerate`` sees no
difference and ``test_model_definitions_match_ddl`` is unaffected — the schema is identical before
and after. What changes is only what one role may do.

**What this does NOT give the service: the full actor chain.** It can write ``executed_by`` and
``execution_method`` — the clause `FR-INTEG-024` names — but ``requested_by_oid`` and
``approved_by_oid`` live on ``work_item`` and ``approval``, which this principal cannot read and
must not be granted (``ragcore/tests/security/test_integration_grants.py`` asserts both refusals).
Those two columns are therefore written NULL by this writer. ``ActorChain`` already declares both
optional and states that ``None`` is itself an audit answer — but a ``None`` here means *unavailable
to this writer*, which is not the same fact as *nobody approved it*. That residual is tracked as
**T327** rather than left for a reader to discover.
"""

from __future__ import annotations

from alembic import op

revision: str = "0024_integrations_audit_grant"
down_revision: str | None = "0023_integration_execution"
branch_labels: str | None = None
depends_on: str | None = None

SCHEMA = "platform"
AUDIT_TABLE = "audit_event"
INTEGRATIONS = "synthia_integrations"

# noqa on the interpolations below for the same reason as revisions 0019 and 0021: a DCL identifier
# — a role name, a schema, a table — CANNOT be a bound parameter in PostgreSQL, so there is no
# parameterised form of GRANT to prefer. Every value interpolated here is a module-level constant
# declared above; none reaches this file from a request, a row or the environment.


def upgrade() -> None:
    """Grant INSERT, and only INSERT."""
    op.execute(f"GRANT INSERT ON {SCHEMA}.{AUDIT_TABLE} TO {INTEGRATIONS}")  # noqa: S608


def downgrade() -> None:
    """Revoke everything this revision could have granted.

    ``REVOKE ALL`` rather than ``REVOKE INSERT``: a downgrade that revoked only what this revision
    granted would leave anything a later hotfix added in place, and the point of a downgrade is to
    return the principal to the privilege set it had before. It held none on this table.
    """
    op.execute(f"REVOKE ALL ON {SCHEMA}.{AUDIT_TABLE} FROM {INTEGRATIONS}")  # noqa: S608
