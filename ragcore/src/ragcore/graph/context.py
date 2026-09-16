"""Run-scoped trusted context: established at the transport boundary, never checkpointed.

LangGraph distinguishes *state* (durable, checkpointed, written by nodes) from *context*
(run-scoped, supplied at invocation, read-only to nodes). The platform needs that distinction for
a reason the framework did not have in mind:

**The tenant binding must not be checkpointed, and must not be writable by a node.**

:class:`~ragcore.domain.tenancy.TenantContext` is constructible only through classmethods that
name their provenance — ``from_admitted_identity``, ``from_work_item``,
``from_platform_object``. There is deliberately no ``from_request`` and no ``parse``. If the
tenant travelled in the checkpoint as a string, resuming a run would mean rebuilding that context
from a value that has lost its provenance, and the only way to do so would be to add the
constructor the domain refuses to have.

Carrying it as run context instead means the binding is re-established from a trusted source on
every invocation — from the validated identity for an interactive turn, from the durable work
item for a resume — and a node that wants to change which organisation a run touches has no
channel to write to.
"""

from __future__ import annotations

from dataclasses import dataclass

from ragcore.domain.identifiers import CorrelationId, PrincipalId, SessionId, WorkItemId
from ragcore.domain.tenancy import TenantContext


@dataclass(frozen=True, slots=True)
class RunContext:
    """The trusted bindings for one graph invocation.

    Attributes:
        tenant: The organisation this run acts within. Re-established per invocation from a
            source that names its provenance.
        requester: The end user the work belongs to — the work item's ``requested_by_oid``.
            Consent may be given only by this principal (spec FR-INTR-005), and the gate compares
            against this value rather than against anything in the conversation.
        correlation_id: Carried onto every log, span, trigger, notification and audit record.
        session_id: The chat session this run serves.
        work_item_id: The durable authority record, once one exists. ``None`` before the triage
            gate commits one — a work record is committed only when the user has articulated a
            genuine request (spec FR-SESS-003), not on the first message.
    """

    tenant: TenantContext
    requester: PrincipalId
    correlation_id: CorrelationId
    session_id: SessionId
    work_item_id: WorkItemId | None = None
