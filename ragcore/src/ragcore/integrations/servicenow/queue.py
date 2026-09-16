"""Where a case write waits when the system of record is unreachable.

If the system of record is unavailable, writes MUST queue and replay rather than being lost, and an
outage MUST NOT block the agent loop — but a session that cannot commit a case MUST NOT proceed to
resolution and the user MUST be told (spec FR-EXT-007). Three obligations, and they pull in
different directions: the loop continues, the write survives, and the session does not resolve.

:class:`CaseWriteQueuePort` is what holds the write. It is declared here rather than in
``application/`` because its consumer is the ServiceNow adapter, and ports belong to the consuming
module (constitution Principle V). Nothing in the agent loop enqueues a case write; the loop calls
:class:`~ragcore.integrations.servicenow.adapter.ServiceNowAdapter`, which decides.

**The durable implementation is not in this module, and its absence is stated rather than
disguised.** A queue that survives a crash is a table, a claim and a dispatcher — which the platform
already has, in :mod:`ragcore.messaging.outbox`, for a different message shape. The scaffold ships
:class:`InMemoryCaseWriteQueue`, which does **not** survive a restart and says so in its own name
and in every line of its docstring. A queue that quietly lost writes while looking durable would be
worse than none: the failure would appear as a case missing progress, weeks later, with nothing
pointing here (constitution Principle IX — scaffold honestly, do not invent product).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ragcore.domain.identifiers import CorrelationId, IdempotencyKey, TenantId


@dataclass(frozen=True, slots=True)
class PendingCaseWrite:
    """One write held for replay.

    Frozen: a write that was edited while queued is a write that no longer matches the idempotency
    key it was recorded under, which is how a replay double-posts.

    Attributes:
        tenant_id: The organisation the write belongs to. A replay is performed under the same
            organisation, resolved from here rather than from whatever context the dispatcher
            happens to be running in.
        case_reference: The case in the system of record.
        facts: What to write. Platform vocabulary only — no table and no ``sys_id``.
        idempotency_key: What makes the replay safe. **The same key as the original attempt**: a
            regenerated key would make a replay a second write (spec FR-EXT-004).
        correlation_id: The journey, so a replayed write is still traceable to the session.
        queued_at: When it was queued, for age-based alerting.
    """

    tenant_id: TenantId
    case_reference: str
    facts: Mapping[str, str]
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId
    queued_at: datetime


@runtime_checkable
class CaseWriteQueuePort(Protocol):
    """Somewhere a case write survives an outage."""

    async def enqueue(self, write: PendingCaseWrite) -> None:
        """Hold a write for replay.

        Raises:
            Exception: When the write cannot be held. **Not swallowed.** A queue that silently
                drops is the failure mode this port exists to prevent, and a caller that cannot
                queue must learn it so the session does not proceed to resolution.
        """
        ...

    async def pending_for(self, tenant_id: TenantId) -> int:
        """How many writes are waiting for this organisation.

        Exists so a session can ask whether its case is committed before resolving. A count rather
        than the writes themselves: the caller needs to know *whether*, and handing it the contents
        would invite it to replay them outside the dispatcher.
        """
        ...


class InMemoryCaseWriteQueue:
    """A queue that lives in this process and **does not survive a restart**.

    Satisfies :class:`CaseWriteQueuePort`. It is honest scaffolding, not a durable store, and the
    distinction matters at exactly one moment: a replica restarting during an outage loses whatever
    it held.

    What it does provide is the *shape* — the adapter's queue-and-replay path is real, the session's
    "is my case committed" question is answerable, and substituting a durable implementation is a
    constructor argument in the composition root rather than a change to the adapter.
    """

    def __init__(self) -> None:
        self._writes: list[PendingCaseWrite] = []

    async def enqueue(self, write: PendingCaseWrite) -> None:
        """Hold a write in memory."""
        self._writes.append(write)

    async def pending_for(self, tenant_id: TenantId) -> int:
        """How many writes are waiting for this organisation."""
        return sum(1 for write in self._writes if write.tenant_id == tenant_id)

    async def drain(self) -> list[PendingCaseWrite]:
        """Take everything held, for a replay pass.

        Not part of :class:`CaseWriteQueuePort`: the port is what the adapter needs, and the adapter
        has no business replaying. This is what a dispatcher would call, and it is on the concrete
        class so that the narrower port stays narrow.
        """
        drained = list(self._writes)
        self._writes.clear()
        return drained
