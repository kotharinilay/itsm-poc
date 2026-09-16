"""The RagCore composition root.

THE ONLY place adapters are constructed and bound to the ports they implement
(plan §Composition roots). FastAPI ``Depends`` resolves from here and constructs nothing itself;
no module outside this one instantiates a concrete adapter.

Service Locator is prohibited. A dependency that cannot be reached from this module is a
dependency nothing should be using.

**Every binding is ``None`` in the scaffold, and that is the honest state.** Stages 7 through 9
bring the adapters — persistence, messaging, integrations. Until then the ports are declared, the
graph is wired in their terms, and the tests substitute fakes. What this module must never do is
supply a default: a retrieval port that quietly returned an empty list, or a catalogue that
answered ``AUTO``, would let the platform appear to work while no boundary was real.

Scaffold honestly; do not invent product (constitution Principle IX).
"""

from __future__ import annotations

from dataclasses import dataclass

from ragcore.application.ports import (
    ApprovalRepositoryPort,
    AuditSinkPort,
    ClockPort,
    ConsentRepositoryPort,
    ModelPort,
    NotificationPort,
    OperationCataloguePort,
    OutboxPort,
    RetrievalPort,
    TenantRegistryPort,
    ToolExecutionPort,
    WorkItemRepositoryPort,
)
from ragcore.config.settings import Settings, get_settings
from ragcore.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class Container:
    """Every constructed adapter, bound to the port it satisfies.

    Frozen, so a caller cannot reach in and swap a binding at runtime. Slotted, so a typo
    assigning a binding fails rather than creating an attribute nothing reads.

    Attributes:
        settings: The validated configuration. The only place any component sees it.
        clock: The system clock. The one adapter that exists in the scaffold, because it needs no
            infrastructure — and because the alternative is ``datetime.now`` scattered around.
        tenant_registry: Registry state for admission. ``None`` until Stage 7.
        work_items: Durable authority records. ``None`` until Stage 7.
        approvals: Staff verdicts. ``None`` until Stage 7.
        consents: End-user consents. ``None`` until Stage 7.
        catalogue: The operation catalogue and per-organisation entitlement. ``None`` until
            Stage 7 — and while it is ``None`` no operation resolves, which means no operation
            executes. Failing closed by construction.
        retrieval: Grounding evidence. ``None`` until the index exists.
        model: Model access through the AI Gateway. ``None`` until Stage 9.
        execution: Governed capability invocation. ``None`` until Stage 9 — so the scaffold
            cannot perform an ITSM operation even if something reached the execution node.
        outbox: The transactional outbox. ``None`` until Stage 8.
        notifications: Realtime delivery. ``None`` until Stage 8.
        audit: Durable audit records. ``None`` until Stage 7.
    """

    settings: Settings
    clock: ClockPort

    tenant_registry: TenantRegistryPort | None = None
    work_items: WorkItemRepositoryPort | None = None
    approvals: ApprovalRepositoryPort | None = None
    consents: ConsentRepositoryPort | None = None
    catalogue: OperationCataloguePort | None = None
    retrieval: RetrievalPort | None = None
    model: ModelPort | None = None
    execution: ToolExecutionPort | None = None
    outbox: OutboxPort | None = None
    notifications: NotificationPort | None = None
    audit: AuditSinkPort | None = None


def build_container(settings: Settings | None = None) -> Container:
    """Construct the container once, at application startup.

    Called from the FastAPI lifespan handler. Once, at startup, rather than per request: a
    configuration failure belongs to a deployment, and an adapter constructed lazily would move
    it to whichever endpoint happened to be hit first.

    Args:
        settings: Validated configuration. Resolved from the environment when omitted; passed
            explicitly by tests, which is why the parameter exists rather than the function
            reaching for :func:`~ragcore.config.settings.get_settings` unconditionally.

    Returns:
        The container, with every adapter this stage has.
    """
    return Container(
        settings=settings if settings is not None else get_settings(),
        clock=SystemClock(),
    )
