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

from sqlalchemy.ext.asyncio import AsyncEngine

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
from ragcore.persistence.engine import create_engine, create_session_factory
from ragcore.persistence.repositories import (
    ApprovalRepository,
    AuditSink,
    ConsentRepository,
    OperationCatalogue,
    Outbox,
    TenantRegistry,
    WorkItemRepository,
)


@dataclass(frozen=True, slots=True)
class Container:
    """Every constructed adapter, bound to the port it satisfies.

    Frozen, so a caller cannot reach in and swap a binding at runtime. Slotted, so a typo
    assigning a binding fails rather than creating an attribute nothing reads.

    Attributes:
        settings: The validated configuration. The only place any component sees it.
        clock: The system clock. The one adapter that exists in the scaffold, because it needs no
            infrastructure — and because the alternative is ``datetime.now`` scattered around.
        engine: The one PostgreSQL engine. Constructed here and disposed by the lifespan that owns
            it, because a pool nobody closes is a file-descriptor leak that only appears under
            load.
        tenant_registry: Registry state for admission. **Stage 7 — bound.**
        work_items: Durable authority records. **Stage 7 — bound.**
        approvals: Staff verdicts. **Stage 7 — bound.**
        consents: End-user consents. **Stage 7 — bound.**
        catalogue: The operation catalogue and per-organisation entitlement. **Stage 7 — bound**,
            and it resolves nothing for an organisation with no entitlement row, so the platform
            still fails closed.
        outbox: The transactional outbox. **Stage 7 — bound.** Publication is Stage 8; durability
            is here, and the two are separate on purpose.
        audit: Durable audit records. **Stage 7 — bound.**
        retrieval: Grounding evidence. ``None`` until the index exists.
        model: Model access through the AI Gateway. ``None`` until Stage 9.
        execution: Governed capability invocation. ``None`` until Stage 9 — so the scaffold
            cannot perform an ITSM operation even if something reached the execution node.
        notifications: Realtime delivery. ``None`` until Stage 8.
    """

    settings: Settings
    clock: ClockPort

    engine: AsyncEngine | None = None
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
    resolved = settings if settings is not None else get_settings()

    # The engine is constructed, not connected. `create_async_engine` opens nothing until the
    # first query, so building a container is still a pure configuration step — which is what
    # keeps a container constructible in a test that never touches a database.
    engine = create_engine(resolved.database)
    sessions = create_session_factory(engine)

    return Container(
        settings=resolved,
        clock=SystemClock(),
        engine=engine,
        # Every repository takes the same session factory and holds no state of its own. They are
        # separate classes rather than one facade because a generic repository would give every
        # aggregate a `get(id)` with no tenant in it.
        tenant_registry=TenantRegistry(sessions),
        work_items=WorkItemRepository(sessions),
        approvals=ApprovalRepository(sessions),
        consents=ConsentRepository(sessions),
        catalogue=OperationCatalogue(sessions),
        outbox=Outbox(sessions),
        audit=AuditSink(sessions),
        # Still `None`, and still honestly so: retrieval has no index, the model has no gateway,
        # execution has no capability to invoke and notifications have no transport. A default
        # that returned an empty list or answered `AUTO` would let the platform appear to work
        # while no boundary was real.
    )
