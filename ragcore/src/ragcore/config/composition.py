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
from ragcore.config.secrets import (
    KeyVaultSecretResolver,
    SecretRef,
    SecretResolutionError,
    SecretResolverPort,
    SecretValue,
)
from ragcore.config.settings import Settings, get_settings
from ragcore.graph.dependencies import GraphDependencies
from ragcore.infrastructure.cache import NullCache, RedisTransientCache, TransientCachePort
from ragcore.infrastructure.clock import SystemClock
from ragcore.integrations.credentials import TenantCredentialResolver
from ragcore.integrations.graph.adapter import MicrosoftGraphAdapter
from ragcore.integrations.http import HttpClientFactory, ResilientHttpCaller
from ragcore.integrations.mcp.client import McpToolClient
from ragcore.integrations.model.adapter import GatewayModelAdapter
from ragcore.integrations.model.egress import ModelEgressPort
from ragcore.integrations.model.gateway import AiGatewayEgress
from ragcore.integrations.model.local import LocalDevelopmentEgress
from ragcore.persistence.engine import UnitOfWork, create_engine, create_session_factory
from ragcore.persistence.repositories import (
    ApprovalRepository,
    AuditSink,
    ConsentRepository,
    EntitlementCredentials,
    FeedbackRepository,
    OperationCatalogue,
    Outbox,
    TenantRegistry,
    WorkItemRepository,
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
        execution: Governed capability invocation through MCP. **Stage 9 — bound.** Reached only
            past the governance gate; the client executes and never decides.
        case_system: The system of record. **Stage 9 — bound** when an instance is configured. Not
            an authority: it holds the case, never an approval.
        directory: Microsoft Graph, read-only. **Stage 9 — bound.**
        discovery: What third-party systems advertise. **Stage 9 — bound**, and separate from
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
    credentials = _credential_resolver(resolved, sessions)

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
        execution=McpToolClient(resolved.integrations, caller, credentials),
        discovery=McpToolClient(resolved.integrations, caller, credentials),
        directory=MicrosoftGraphAdapter(resolved.integrations, caller),
        # These two stay `None` when unconfigured rather than getting a stand-in. Retrieval with no
        # index and a case system with no instance are absences a caller must be able to detect: an
        # empty result set would read as "this organisation has nothing", and a silently discarded
        # case write would read as a committed one.
        retrieval=(
            AzureAiSearchRetrieval(resolved.retrieval, caller)
            if resolved.retrieval.is_configured
            else None
        ),
        # Always bound, never `None`. Redis is transient only: it is never an authority and never
        # a durable record, so a process without one is fully correct and simply slower.
        cache=(
            RedisTransientCache(resolved.cache) if resolved.cache.is_configured else NullCache()
        ),
        # THE DIRECT SERVICENOW PATH IS GONE (ADR-0007, spec §22.1). RagCore no longer calls the
        # system of record: it calls the Integrations Service, through APIM, and that service owns
        # every connector, every credential and every egress path.
        #
        # `None` rather than a stand-in, and deliberately so. The `CaseSystemPort` binding that used
        # to hold `ServiceNowAdapter` has no in-process implementation any more and must not gain
        # one — an adapter here would be exactly the direct path the boundary removes. Case
        # operations go through `ragcore.platform_clients.integrations.IntegrationsClient`, which
        # is bound separately below because it is a **platform service client**, not a connector.
        #
        # A silently discarded case write would read as a committed one, so a caller that finds
        # this `None` escalates rather than proceeding.
        case_system=None,
        # Still `None`, and still honestly so: notifications have no transport until Stage 8 binds
        # one here. A default that quietly dropped them would let the platform appear to work while
        # no boundary was real.
    )


def _model_egress(settings: Settings, caller: ResilientHttpCaller) -> ModelEgressPort:
    """Choose the model egress. **The only place in this platform where that choice is made.**

    Two outcomes, and there is deliberately no third:

    * A gateway is configured — :class:`~ragcore.integrations.model.gateway.AiGatewayEgress`.
    * No gateway is configured — :class:`~ragcore.integrations.model.local.LocalDevelopmentEgress`,
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


def _credential_resolver(
    settings: Settings, sessions: async_sessionmaker[AsyncSession]
) -> TenantCredentialResolver:
    """Build per-organisation credential resolution: a reference from PostgreSQL, a value from Key
    Vault.

    Args:
        settings: The validated configuration.
        sessions: The session factory the reference store reads through.

    Returns:
        The resolver every third-party adapter takes. It holds no credential itself — it resolves
        one, per organisation, at the point of use (spec FR-EXT-016).
    """
    secrets: SecretResolverPort = (
        KeyVaultSecretResolver(settings.key_vault.vault_uri)
        if settings.key_vault.is_configured
        else _NoVaultResolver()
    )
    return TenantCredentialResolver(EntitlementCredentials(sessions), secrets)


class _NoVaultResolver:
    """What resolves a secret when no vault is configured: **nothing, loudly.**

    Satisfies :class:`~ragcore.config.secrets.SecretResolverPort` by always raising. A developer
    machine legitimately has no vault, and the honest consequence is that a call needing an
    organisation's credential fails with a message naming the missing vault — not that it proceeds
    unauthenticated, and not that it falls back to an environment variable, which would be a
    credential in configuration.
    """

    async def resolve(self, ref: SecretRef) -> SecretValue:
        """Raise, naming the reference that could not be resolved.

        Raises:
            SecretResolutionError: Always. There is no vault to resolve from.
        """
        raise SecretResolutionError(
            ref.name,
            "no vault",
            "no Key Vault is configured for this process, and there is no other source of secret "
            "material. Set SYNTHIA_KEYVAULT_VAULT_URI",
        )


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
