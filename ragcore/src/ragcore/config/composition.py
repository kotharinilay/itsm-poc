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

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ragcore.application.ports import (
    ApprovalRepositoryPort,
    AuditSinkPort,
    CapabilityDiscoveryPort,
    CaseSystemPort,
    ClockPort,
    ConsentRepositoryPort,
    DirectoryPort,
    FeedbackRepositoryPort,
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
from ragcore.egress.http import HttpClientFactory, ResilientHttpCaller
from ragcore.graph.dependencies import GraphDependencies
from ragcore.infrastructure.cache import NullCache, RedisTransientCache, TransientCachePort
from ragcore.infrastructure.clock import SystemClock
from ragcore.model.adapter import GatewayModelAdapter
from ragcore.model.egress import ModelEgressPort
from ragcore.model.gateway import AiGatewayEgress
from ragcore.model.local import LocalDevelopmentEgress
from ragcore.persistence.engine import UnitOfWork, create_engine, create_session_factory
from ragcore.persistence.repositories import (
    ApprovalRepository,
    AuditSink,
    ConsentRepository,
    FeedbackRepository,
    OperationCatalogue,
    Outbox,
    TenantRegistry,
    WorkItemRepository,
)
from ragcore.platform_clients.integrations import (
    IntegrationsClient,
    IntegrationsClientSettings,
)
from ragcore.retrieval.search import AzureAiSearchRetrieval


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
        http: The pooled outbound HTTP clients. **Stage 9 — bound**, and owned by the lifespan
            that built this container: every adapter takes a client from here, so nothing
            constructs one per call and no integration's timeouts are its own invention.
        retrieval: Grounding evidence from the derived index. **Stage 9 — bound** when an index is
            configured, and ``None`` otherwise. ``None`` rather than an empty-result stand-in: a
            grounding node that received an empty list could not tell "this organisation has no
            matching knowledge" from "this process cannot retrieve".
        model: Model access through the AI Gateway. **Stage 9 — bound, always.** Either the gateway
            client or, on a developer machine with no gateway, the local development seam that
            calls no model. **There is deliberately no third option and no provider client** —
            RagCore holds no model provider role at all
            (``build/infra/identity/managed-identities.json``).
        execution: Governed capability invocation. **Always ``None`` in this process** — the
            binding that used to hold an MCP client was removed with the connector boundary
            (T296, ADR-0007). Capabilities execute in the Integrations Service, reached over
            Service Bus; the port survives because the graph node and its tests are written against
            it, and a **test double** satisfying it is legitimate where a production adapter is not.
        case_system: The system of record. **Always ``None``.** See the note at the binding below.
        directory: Directory reads. **Always ``None``** — Microsoft Graph moved to the Integrations
            Service with every other connector (T289).
        discovery: What third-party systems advertise. **Always ``None``** — discovery is an MCP
            call, and MCP calls are made by the Integrations Service. The port stays separate from
            ``catalogue`` on purpose: discovery confers no entitlement, and one port returning both
            would make the two indistinguishable at the call site.
        notifications: Realtime delivery. ``None`` until Stage 8.
        cache: The transient cache. **Stage 10 — always bound**, to Redis when a host is configured
            and to :class:`~ragcore.infrastructure.cache.NullCache` otherwise. Never ``None``,
            unlike every other optional binding above, and the difference is deliberate: a caller
            must never branch on whether a cache exists. A cache miss and an absent cache lead to
            the same code path — do the work — so an always-missing cache is the honest
            representation of "no cache", and nothing can come to depend on one being there.
    """

    settings: Settings
    clock: ClockPort

    engine: AsyncEngine | None = None
    http: HttpClientFactory | None = None
    tenant_registry: TenantRegistryPort | None = None
    work_items: WorkItemRepositoryPort | None = None
    approvals: ApprovalRepositoryPort | None = None
    consents: ConsentRepositoryPort | None = None
    feedback: FeedbackRepositoryPort | None = None
    catalogue: OperationCataloguePort | None = None
    retrieval: RetrievalPort | None = None
    model: ModelPort | None = None
    execution: ToolExecutionPort | None = None
    case_system: CaseSystemPort | None = None
    directory: DirectoryPort | None = None
    discovery: CapabilityDiscoveryPort | None = None
    outbox: OutboxPort | None = None
    notifications: NotificationPort | None = None
    audit: AuditSinkPort | None = None
    cache: TransientCachePort = field(default_factory=NullCache)

    integrations: IntegrationsClient | None = None
    """The Integrations Service, through APIM. **RagCore's only synchronous route outward.**

    Bound when an edge address is configured, ``None`` otherwise — and ``None`` here is not the same
    kind of absence as the connector bindings above. Those are permanently ``None`` by design; this
    one is ``None`` only because no route is configured for this process, and a caller that finds it
    so reports the capability as unavailable rather than proceeding.

    **It is not a connector, which is why it may exist at all.** The thing at the other end is a
    sibling platform service reached through the gateway, not a customer system reached directly.
    """

    sessions: async_sessionmaker[AsyncSession] | None = None
    """The session factory every repository was built with.

    Held so :meth:`unit_of_work` can open a transaction. It is **not** a port and no application
    module receives it: ``application/ports.py`` is stated in domain terms, and an ``AsyncSession``
    parameter there would put SQLAlchemy in the application layer. What crosses that boundary is
    :class:`~ragcore.application.ports.UnitOfWorkPort`, which is what this returns.
    """

    def unit_of_work(self) -> UnitOfWork:
        """Open a transaction.

        **The only way a write path begins**, because the transactional outbox depends on an outbox
        row landing in the same transaction as the state change it describes. A repository that
        opened its own session would break that without failing, which is why
        :func:`~ragcore.persistence.engine.current_session` refuses a write with no boundary open.

        Raises:
            RuntimeError: When this container was built without persistence — a test double, or a
                worker that has no database. Raised rather than returning a no-op boundary, because
                a no-op boundary is a write that silently does not commit.
        """
        if self.sessions is None:
            raise RuntimeError(
                "this container has no session factory, so no transaction can be opened. A write "
                "path needs persistence; there is no in-memory fallback, because a boundary that "
                "commits nothing is worse than one that is absent."
            )
        return UnitOfWork(self.sessions)

    async def aclose(self) -> None:
        """Release what this container owns.

        Called from the application lifespan on shutdown, and by a worker's own context manager.
        Only the HTTP pool is released here; the engine and the shared Azure credential are
        disposed by the lifespan, which has always owned them.
        """
        if self.http is not None:
            await self.http.aclose()


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

    # One factory, one resilience policy, one pool per named integration. No adapter below builds
    # an HTTP client, which is what makes "every outbound call carries an explicit timeout" a
    # property of the transport rather than a rule each adapter author remembered (research R-020).
    http = HttpClientFactory()
    caller = ResilientHttpCaller(http)

    clock = SystemClock()

    return Container(
        settings=resolved,
        clock=clock,
        engine=engine,
        sessions=sessions,
        http=http,
        # Every repository takes the same session factory and holds no state of its own. They are
        # separate classes rather than one facade because a generic repository would give every
        # aggregate a `get(id)` with no tenant in it.
        tenant_registry=TenantRegistry(sessions),
        work_items=WorkItemRepository(sessions),
        approvals=ApprovalRepository(sessions),
        consents=ConsentRepository(sessions),
        feedback=FeedbackRepository(sessions),
        catalogue=OperationCatalogue(sessions),
        outbox=Outbox(sessions),
        audit=AuditSink(sessions),
        # Stage 9. Every external system behind an explicit port, and every one of them reached
        # through the shared HTTP caller above.
        #
        # `model` is bound unconditionally and the selection is made by `_model_egress`, which is
        # the one function allowed to decide it. Leaving it `None` when no gateway is configured
        # would put the decision back at the call sites, where the tempting resolution is a
        # provider client.
        model=GatewayModelAdapter(_model_egress(resolved, caller)),
        # Retrieval stays `None` when unconfigured rather than getting a stand-in: an empty result
        # set would read as "this organisation has nothing" rather than "this process cannot
        # retrieve", and those are different facts.
        retrieval=(
            AzureAiSearchRetrieval(resolved.retrieval, caller)
            if resolved.retrieval.is_configured
            else None
        ),
        # Always bound, never `None`. Redis is transient only: it is never an authority and never
        # a durable record, so a process without one is fully correct and simply slower.
        # THE REPLACEMENT FOR EVERY BINDING REMOVED ABOVE. Synchronous integration work — the
        # catalogue read, the system-of-record operation — goes through here, over APIM. The
        # asynchronous path needs no binding at all: it writes an `integration_job` row and
        # publishes the job identifier, and `ragcore.persistence.integration_jobs` owns that.
        integrations=(
            IntegrationsClient(
                IntegrationsClientSettings(
                    gateway_base_url=resolved.integrations.gateway_base_url,
                    entra_scope=resolved.integrations.entra_scope,
                ),
                caller,
            )
            if resolved.integrations.is_configured
            else None
        ),
        cache=(
            RedisTransientCache(resolved.cache) if resolved.cache.is_configured else NullCache()
        ),
        # EVERY CONNECTOR BINDING IS `None`, AND THAT IS THE BOUNDARY (ADR-0007, spec §22.1,
        # `FR-INTEG-016`). RagCore calls no external system. It calls the Integrations Service
        # through APIM for the synchronous paths, and dispatches a durable job over Service Bus for
        # the asynchronous ones; that service owns every connector, every credential and every
        # egress path.
        #
        # `None` rather than a stand-in, and deliberately so. A stand-in is an object with a method
        # to call, and the first caller to call it would have re-created in-process exactly the
        # path this removes. These four MUST NOT gain an in-process implementation:
        #
        #   case_system  — was `ServiceNowAdapter`      → `integrations.connectors.servicenow`
        #   directory    — was `MicrosoftGraphAdapter`  → `integrations.connectors.graph`
        #   execution    — was `McpToolClient`          → `integrations.mcp.client`
        #   discovery    — was `McpToolClient`          → `integrations.mcp.client`
        #
        # Enforced rather than asked for: `tests/architecture/test_no_connector_in_ragcore.py`
        # fails if one is bound here, and `build/scripts/check-boundaries.sh` fails the build if
        # the code to bind reappears in this tree at all.
        #
        # A silently discarded write would read as a committed one, so a caller that finds one of
        # these `None` escalates rather than proceeding.
        case_system=None,
        directory=None,
        execution=None,
        discovery=None,
        # Still `None`, and still honestly so: notifications have no transport until Stage 8 binds
        # one here. A default that quietly dropped them would let the platform appear to work while
        # no boundary was real.
    )


def _model_egress(settings: Settings, caller: ResilientHttpCaller) -> ModelEgressPort:
    """Choose the model egress. **The only place in this platform where that choice is made.**

    Two outcomes, and there is deliberately no third:

    * A gateway is configured — :class:`~ragcore.model.gateway.AiGatewayEgress`.
    * No gateway is configured — :class:`~ragcore.model.local.LocalDevelopmentEgress`,
      which calls no model and refuses to be constructed outside local development.

    **A provider client is not among the options**, here or anywhere. RagCore holds no Foundry role
    (``build/infra/identity/managed-identities.json``), so a direct provider call would fail to
    authenticate even if the code existed — and the code does not exist, which
    ``tests/architecture/test_no_direct_model_call.py`` asserts.

    Args:
        settings: The validated configuration.
        caller: The shared resilient HTTP caller.

    Returns:
        The egress every model call in this process will cross.

    Raises:
        ModelEgressError: When no gateway is configured and the environment is not local. A
            deployed process that answered model calls without a model would meter nothing and look
            entirely healthy; this makes it a container that does not start.
    """
    if settings.gateway.is_configured:
        return AiGatewayEgress(settings.gateway, caller)

    return LocalDevelopmentEgress(environment=settings.environment)


# THERE IS NO CREDENTIAL RESOLVER IN THIS PROCESS, AND ITS ABSENCE IS THE CONTROL.
#
# `_credential_resolver` and its no-vault stand-in used to sit here, resolving a per-organisation
# connector secret: a reference from `tenant_entitlement`, a value from Key Vault. Both are gone
# with the connector boundary (T296, ADR-0007, spec `FR-INTEG-017`).
#
# **The removal is not only of code.** `id-synthia-ragcore` no longer holds the vault role for
# connector secrets — it was narrowed to `secret:synthia-ragcore-*` rather than duplicated
# (`build/infra/identity/managed-identities.json`), and `vw_connector_credential_ref_v1` is granted
# to the Integrations principal alone. That withdrawal is what makes `SC-DEMO-020` provable: the
# bypass test attempts the resolution from RagCore and observes Key Vault refuse it, which is a
# fact about deployed authorization rather than about which code happens to exist.
#
# RagCore still resolves *its own* secrets — a database password, a gateway key — through
# `ragcore.config.secrets`. The distinction that matters is whose system the secret opens.


def graph_dependencies(container: Container) -> GraphDependencies | None:
    """Assemble what the graph is bound to, or report that this process cannot host one.

    **Every field is required and none is defaulted.** A graph compiled with a stand-in for a
    missing adapter is a graph that runs and quietly does less than it appears to — an empty
    retrieval leg looks like an organisation with no knowledge, and a no-op execution port looks
    like an operation that succeeded. Returning ``None`` instead makes "this process does not host
    a run loop" a fact the caller has to handle.

    Args:
        container: The constructed adapters.

    Returns:
        The dependencies, or ``None`` when any of them is unbound. The scaffold binds no tool
        execution adapter — **no autonomous ITSM operation is implemented** — so a scaffold process
        legitimately returns ``None`` here, and the conversation surface reports an honest empty
        stream rather than inventing progress.
    """
    required = (
        container.catalogue,
        container.retrieval,
        container.model,
        container.work_items,
        container.approvals,
        container.consents,
        container.execution,
        container.audit,
    )
    if any(binding is None for binding in required):
        return None

    catalogue, retrieval, model, work_items, approvals, consents, execution, audit = required
    assert catalogue is not None  # noqa: S101 — narrowing for the type checker, checked above
    assert retrieval is not None  # noqa: S101
    assert model is not None  # noqa: S101
    assert work_items is not None  # noqa: S101
    assert approvals is not None  # noqa: S101
    assert consents is not None  # noqa: S101
    assert execution is not None  # noqa: S101
    assert audit is not None  # noqa: S101

    return GraphDependencies(
        clock=container.clock,
        catalogue=catalogue,
        retrieval=retrieval,
        model=model,
        work_items=work_items,
        approvals=approvals,
        consents=consents,
        execution=execution,
        audit=audit,
    )
