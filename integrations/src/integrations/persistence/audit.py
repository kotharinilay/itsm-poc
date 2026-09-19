"""Durable audit for one external invocation. **One store, and this service appends to it.**

`FR-INTEG-024`, migration 0024, T326.

**Audit does not fork.** This writes into ``platform.audit_event`` — the platform's single audit
store, the same table RagCore writes — rather than into this service's own schema. A second audit
store would mean two answers to "what happened", and the reconciliation between them would be a
report nobody runs.

**Distinct from the execution record, and both are needed.**
:mod:`integrations.persistence.executions` records *what this service attempted against which
connector*: the derived key, the endpoint, the normalized outcome. That is an operational record in
this service's own schema. This is the *governance* record: who did it, by what means, against which
organisation, with what result — retained on the audit schedule and readable by the staff surface
through ``vw_audit_event_v1``. Collapsing them would force one retention policy and one access
grant onto two different questions.

**INSERT only. This module cannot read, amend or delete an audit record**, and the grant is what
makes that true rather than the absence of a method here (migration 0024). Append-only has been this
table's rule since revision 0013; no principal holds ``UPDATE`` or ``DELETE`` on it.

**Written in the caller's transaction**, alongside the execution record and the outbox row. An audit
record that committed separately could survive a rolled-back execution — claiming an effect that
never happened — or be lost while the effect persisted. Neither is recoverable after the fact, which
is why there is no method here that opens its own transaction.

**The actor chain is partial from this writer, and the omission is stated rather than hidden.**
``executed_by`` and ``execution_method`` are this service's to report and are the clause
`FR-INTEG-024` names. ``requested_by_oid`` and ``approved_by_oid`` live on ``work_item`` and
``approval``, which this principal cannot read and must not be granted — so they are written NULL.
:class:`~ragcore.domain.audit.ActorChain` already treats both as optional, but a NULL here means
*unavailable to this writer*, not *nobody approved it*. **T327** carries the residual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from uuid import uuid4

from sqlalchemy import text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from datetime import datetime
    from typing import Any
    from uuid import UUID

    from integrations.domain.execution import ExecutionRecord

__all__ = ["AUDIT_ACTION", "EXECUTED_BY", "AuditWriter"]

EXECUTED_BY: Final = "synthia_integrations"
"""What this service records as the executing principal.

**The database role name, not a display string.** It is the identifier an operator can correlate
with a role assignment, a Key Vault audit entry and a PostgreSQL log line. A friendly name here
would be one more mapping to maintain, and the mapping would be the thing that went stale.
"""

EXECUTION_METHOD: Final = "workload"
"""By what means. The workload principal acting directly — the only mechanism this service
implements. Desktop execution is a different value and is not reachable from here."""

AUDIT_ACTION: Final = "integration.executed"
"""The action recorded, for every outcome including a refusal.

**A refusal is recorded as durably as a success** (spec §28). The ``outcome`` column carries which
it was; the action says what was attempted. An action that differed per outcome would make "how many
executions did we attempt" a query over a set of strings nobody maintains.
"""

_INSERT_AUDIT: Final = text(
    """
    INSERT INTO platform.audit_event (
        audit_id, tenant_id, work_item_id, occurred_at, action,
        requested_by_oid, approved_by_oid,
        executed_by, execution_method, outcome, verification,
        correlation_id, retain_until
    ) VALUES (
        :audit_id, :tenant_id, :work_item_id, :occurred_at, :action,
        NULL, NULL,
        :executed_by, :execution_method, :outcome, :verification,
        :correlation_id, now() + interval '7 years'
    )
    """
)
"""The one statement this module issues.

**The retention horizon is an interval in the statement, not a constant in this module.** It was
briefly both, and a module-level ``_RETENTION_YEARS`` that nothing read was the worse half: the next
author changes it, nothing happens, and the discrepancy is invisible until an audit record is purged
years early. ``now() + interval`` also derives the horizon from the **database's** clock, so two
records written seconds apart on different replicas are retained for the same period.

``requested_by_oid`` and ``approved_by_oid`` are **literal NULLs rather than bound parameters**, and
that is deliberate: there is no argument on :meth:`AuditWriter.record` with which a caller could
supply them. A parameter that only ever receives ``None`` is a parameter somebody eventually fills
from an untrusted source — and this service cannot verify either value, because it cannot read the
records that hold them.
"""


class AuditWriter:
    """Appends one governance record per external invocation."""

    async def record(
        self,
        session: Any,  # An AsyncSession, typed loosely as elsewhere in this layer
        execution: ExecutionRecord,
        *,
        work_item_id: UUID,
        occurred_at: datetime,
    ) -> UUID:
        """Append the audit record, **in the caller's transaction**.

        Args:
            session: The caller's transaction — the same one as the execution record and the outbox
                row, so the three are durable together or not at all.
            execution: What was attempted and what is known about it. The organisation, the
                outcome and the verification all come from here, having been **recovered from
                durable state** rather than from the message that triggered the work.
            work_item_id: The authority record this execution spent. Recorded so an auditor can
                join to the decision that permitted it, even though this writer cannot read that
                decision itself.
            occurred_at: When the effect was attempted. Passed in rather than taken from a clock
                here, so it matches the execution record's own timestamp exactly — two timestamps
                for one event, differing by milliseconds, is a reconciliation nobody can complete.

        Returns:
            The audit identifier, so the caller can correlate it in telemetry without re-reading a
            table it holds no ``SELECT`` on.
        """
        audit_id = uuid4()

        await session.execute(
            _INSERT_AUDIT,
            {
                "audit_id": audit_id,
                "tenant_id": execution.tenant_id,
                "work_item_id": work_item_id,
                "occurred_at": occurred_at,
                "action": AUDIT_ACTION,
                "executed_by": EXECUTED_BY,
                "execution_method": EXECUTION_METHOD,
                # The normalized outcome, not the provider's own words. A vendor error string in an
                # audit record is untrusted text in a governance store — and `outcome` is bounded
                # at 256 characters, which a provider body is not.
                "outcome": execution.outcome.value,
                "verification": execution.verification.value,
                "correlation_id": execution.correlation_id,
            },
        )

        return audit_id
