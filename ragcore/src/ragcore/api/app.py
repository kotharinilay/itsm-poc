"""The FastAPI application factory.

A factory rather than a module-level ``app``, so a test constructs an application with its own
settings without setting environment variables and without a global that imports have already
bound. It is also what keeps the composition root honest: the container is built once, here, and
attached to ``app.state`` for :mod:`ragcore.api.deps` to resolve from.

**Middleware order matters and is not arbitrary.** Starlette applies them outermost-last, so the
list below runs in the order it reads:

1. **Correlation** outermost, so even a request the next layer refuses is correlatable and its
   refusal echoes an identifier a user can quote.
2. **Gateway provenance** next, refusing anything that cannot prove it arrived through APIM. It runs
   *before* identity because identity is only meaningful once provenance holds: the ``X-Idp-*``
   contract is trusted precisely and only because APIM set it, and a request that did not come
   through APIM must be refused before any of it is read.
3. **Identity** last, rejecting self-asserted authority *before* routing — so no endpoint, and no
   dependency, ever sees a request carrying a client-supplied tenant or role.

**Migrations do not run here.** Nothing in this module touches DDL. Migrations run as a gated job
before revision activation (plan §Stage 7), and the checkpointer's ``setup()`` runs from that same
job — a process that provisioned schema on boot would need DDL rights at runtime, which is exactly
what the separated database principals exist to prevent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from ragcore.api.customer.answers import router as answers_router
from ragcore.api.customer.feedback import router as feedback_router
from ragcore.api.customer.negotiate import router as negotiate_router
from ragcore.api.customer.routes import router as customer_router
from ragcore.api.customer.sample_flows import router as sample_flow_router
from ragcore.api.customer.sessions import router as sessions_router
from ragcore.api.health import router as health_router
from ragcore.api.middleware.correlation import CorrelationIdMiddleware
from ragcore.api.middleware.identity import IdentityHeaderMiddleware
from ragcore.api.middleware.problems import install_problem_handlers
from ragcore.api.middleware.provenance import (
    GatewayProvenanceMiddleware,
    require_thumbprints,
)
from ragcore.api.openapi import install_contract_openapi
from ragcore.api.staff.routes import router as staff_router
from ragcore.api.workload.routes import router as workload_router
from ragcore.config.composition import Container, build_container, graph_dependencies
from ragcore.config.secrets import KeyVaultSecretResolver, SecretValue, resolve_required
from ragcore.config.settings import Settings, get_settings
from ragcore.graph.checkpointer import durable_graph
from ragcore.graph.host import RunHost
from ragcore.infrastructure.azure_credentials import close_azure_credential
from ragcore.observability.telemetry import configure_telemetry

TITLE = "Synthia RagCore"
DESCRIPTION = (
    "Orchestration, execution and every state-changing operation. The model proposes; "
    "deterministic governance authorizes."
)


def create_app(*, settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Validated configuration. Resolved from the environment when omitted.
        container: A pre-built container, for tests that bind fakes. When supplied the lifespan
            handler does not build one — which is the only supported way to substitute an
            adapter, and it goes through the composition root's own type rather than around it.

    Returns:
        The application, with middleware, problem handlers and all three audience routers.
    """
    # Settings are resolved HERE rather than only inside the lifespan, because gateway provenance
    # is configured on the middleware and middleware is bound when the application is built. That
    # ordering is deliberate: an allow-list read at request time would make an unconfigured process
    # start cleanly and fail per request, and a security control that degrades into a 403 storm is
    # one that gets switched off under pressure. The lifespan still owns the container.
    resolved_settings = (
        settings
        if settings is not None
        else container.settings
        if container is not None
        else get_settings()
    )

    # Parsed and checked HERE, before anything else is built. `add_middleware` only records the
    # class and its arguments — Starlette constructs the stack on first use — so a check that lived
    # solely in the middleware constructor would fire when the application started *serving*
    # rather than when it was *built*, and the gap between those two moments is exactly where a
    # misconfigured process can look healthy.
    accepted_thumbprints = require_thumbprints(
        resolved_settings.edge_trust.gateway_certificate_thumbprints
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Construct the container once, and release it on shutdown.

        Configuration is validated here, so a malformed setting is a container that does not
        start rather than a ``None`` surfacing on whichever endpoint is hit first
        (research R-019).

        **Cancellation-safe.** Shutdown work belongs after the ``yield``, where Starlette runs it
        during a controlled shutdown. Nothing here catches :class:`asyncio.CancelledError`.
        """
        app.state.container = (
            container if container is not None else build_container(resolved_settings)
        )
        resolved = app.state.container.settings

        # Secret references resolve HERE, before the application begins serving, and a failure
        # stops the process (research R-019). Resolving lazily would fail on whichever request
        # first needed the secret, in whichever replica happened to serve it — a configuration
        # defect wearing the costume of an intermittent outage.
        #
        # Skipped when no vault is configured, which is the developer-machine case and the only
        # one. A deployed environment without a vault is a deployment defect, and the pipeline is
        # what catches it: a running process cannot tell which environment it wishes it were in.
        secrets: Mapping[str, SecretValue] = {}
        if resolved.key_vault.is_configured:
            secrets = await resolve_required(
                KeyVaultSecretResolver(resolved.key_vault.vault_uri),
                resolved.required_secret_references(),
            )

        # Telemetry is configured AFTER secrets resolve and BEFORE the application serves. After,
        # because the Application Insights connection string is one of those secrets and is a
        # credential for a telemetry workspace, so it arrives as a reference like everything else.
        # Before, because a request served by a process with no tracer is a request that is
        # invisible — and it would be the first one, which is the one being debugged.
        configure_telemetry(
            resolved.observability,
            connection_string=secrets.get(resolved.observability.connection_string_secret_name),
        )

        # THE RUN HOST, built once and held for the process lifetime. The graph is compiled
        # against the one durable checkpointer here rather than per request, because a checkpointer
        # opens a PostgreSQL connection and a per-request compile would open one per turn — and
        # because a suspension written by one compiled shape must be resumed by the same one.
        #
        # `graph_dependencies` returns None when any adapter the graph needs is unbound, which in
        # the scaffold is the ordinary case: no tool execution adapter is bound, because no
        # autonomous ITSM operation is implemented. The conversation surface then reports an honest
        # empty stream rather than a run loop that quietly does less than it appears to.
        app.state.run_host = None
        async with AsyncExitStack() as graph_scope:
            deps = graph_dependencies(app.state.container)
            if deps is not None:
                compiled = await graph_scope.enter_async_context(
                    durable_graph(str(resolved.database.dsn), deps)
                )
                app.state.run_host = RunHost(compiled)

            try:
                yield
            finally:
                # The outbound pools go first: they hold live connections to the AI Gateway, the
                # system of record and Graph, and closing the credential out from under an
                # in-flight call would produce an authentication failure on the way down rather
                # than a clean shutdown.
                await app.state.container.aclose()
                # The shared credential owns an HTTP session; a session nobody closes is a warning
                # on every test run and a descriptor leak in a long-lived worker.
                await close_azure_credential()
                app.state.container = None
                app.state.run_host = None

    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        # OpenAPI is generated from the application contracts — the Pydantic schemas on each
        # route — rather than hand-written, so the document cannot drift from what runs.
        openapi_url="/openapi.json",
    )

    # Read bottom-up: Starlette wraps each added middleware around the ones added before it, so
    # the running order is correlation, then provenance, then identity — every request is
    # correlated before anything refuses it, and nothing reads the identity contract until the
    # request has proved it came through the gateway that set it.
    #
    # The allow-list is resolved HERE, at construction, not per request. A process that cannot
    # prove provenance must not start (see GatewayProvenanceUnconfiguredError), and `create_app`
    # is where that failure becomes a container that does not start rather than a 403 storm.
    app.add_middleware(IdentityHeaderMiddleware)
    app.add_middleware(
        GatewayProvenanceMiddleware,
        accepted_thumbprints=accepted_thumbprints,
    )
    app.add_middleware(CorrelationIdMiddleware)

    install_problem_handlers(app)

    # Outside every audience prefix, and outside the trust boundary with it: the probes come from
    # the Container Apps infrastructure on the internal network, not through APIM, so they carry no
    # certificate and no identity. See ragcore.api.health.
    app.include_router(health_router)

    app.include_router(customer_router)
    # The live halves of the customer audience, each in its own module so a live route is never
    # filed beside an inert one. Order is irrelevant to routing — no two of these declare the same
    # path — and is alphabetical so a new one has an obvious place to go.
    app.include_router(answers_router)
    app.include_router(feedback_router)
    app.include_router(sessions_router)
    # Realtime negotiation and the inert sample flow. Both sit on the customer audience: the
    # group a client receives on is derived from trusted identity, and the sample flow is
    # platform plumbing rather than product capability.
    app.include_router(negotiate_router)
    app.include_router(sample_flow_router)
    app.include_router(staff_router)
    app.include_router(workload_router)

    # Installed AFTER every router, because it generates from `app.routes` and caches. The served
    # document and the published artifact then come from one path — two paths is how they come to
    # disagree, and the disagreement surfaces at a client rather than in CI.
    install_contract_openapi(app)

    return app
