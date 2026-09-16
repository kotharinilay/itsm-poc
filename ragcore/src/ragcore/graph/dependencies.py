"""What the graph needs, declared explicitly and passed in.

**Explicit dependency injection, no service locator** (constitution §Dependency injection). The
builder closes over one frozen :class:`GraphDependencies`; no node reaches for a global, a module
singleton or a registry, and there is no container to ask at runtime.

Every field is a Protocol from :mod:`ragcore.application.ports`, so the graph is expressed
entirely in domain terms and a test substitutes a fake without a database, a broker or a model.
The concrete adapters are constructed in :mod:`ragcore.config.composition` and nowhere else.

**The catalogue is here; treatment policy is not.** Catalogue *data* is stored, so reading it is
infrastructure. The treatment *decision* over that data is
:func:`~ragcore.governance.policy.assign_treatment`, a pure function the nodes import directly —
because a decision behind a Protocol is a decision an adapter could implement differently.
"""

from __future__ import annotations

from dataclasses import dataclass

from ragcore.application.ports import (
    ApprovalRepositoryPort,
    AuditSinkPort,
    ClockPort,
    ConsentRepositoryPort,
    ModelPort,
    OperationCataloguePort,
    RetrievalPort,
    ToolExecutionPort,
    WorkItemRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class GraphDependencies:
    """The collaborators one compiled graph is bound to.

    Frozen so a node cannot swap a binding mid-run. Slotted so a typo assigning an attribute
    fails rather than creating one.

    Attributes:
        clock: The current instant. A port so an expiry test does not wait fifteen real minutes,
            and so nothing calls ``datetime.now`` outside an adapter.
        catalogue: Catalogue data and per-organisation entitlement. Returns data only.
        retrieval: Grounding evidence, always tenant-scoped. There is no unfiltered overload.
        model: Reasoning and embeddings, routed exclusively through the AI Gateway.
        work_items: The durable authority records.
        approvals: Staff verdicts. The graph **reads** decisions here; it never records one —
            a verdict enters only through the authenticated staff API (ADR-0002).
        consents: End-user consents, read on the same terms.
        execution: Invocation of a governed capability. Reached only past the gate.
        audit: Durable audit records, separate from telemetry and separately retained.
    """

    clock: ClockPort
    catalogue: OperationCataloguePort
    retrieval: RetrievalPort
    model: ModelPort
    work_items: WorkItemRepositoryPort
    approvals: ApprovalRepositoryPort
    consents: ConsentRepositoryPort
    execution: ToolExecutionPort
    audit: AuditSinkPort
