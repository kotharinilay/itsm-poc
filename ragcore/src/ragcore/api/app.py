"""The FastAPI application factory.

A factory rather than a module-level ``app``, so a test constructs an application with its own
settings without setting environment variables and without a global that imports have already
bound. It is also what keeps the composition root honest: the container is built once, here, and
attached to ``app.state`` for :mod:`ragcore.api.deps` to resolve from.

**Middleware order matters and is not arbitrary.** Starlette applies them outermost-last, so the
list below runs in the order it reads:

1. **Correlation** outermost, so even a request the next layer refuses is correlatable and its
   refusal echoes an identifier a user can quote.
2. **Identity** next, rejecting self-asserted authority *before* routing — so no endpoint, and no
   dependency, ever sees a request carrying a client-supplied tenant or role.

**Migrations do not run here.** Nothing in this module touches DDL. Migrations run as a gated job
before revision activation (plan §Stage 7), and the checkpointer's ``setup()`` runs from that same
job — a process that provisioned schema on boot would need DDL rights at runtime, which is exactly
what the separated database principals exist to prevent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ragcore.api.customer.routes import router as customer_router
from ragcore.api.middleware.correlation import CorrelationIdMiddleware
from ragcore.api.middleware.identity import IdentityHeaderMiddleware
from ragcore.api.middleware.problems import install_problem_handlers
from ragcore.api.staff.routes import router as staff_router
from ragcore.api.workload.routes import router as workload_router
from ragcore.config.composition import Container, build_container
from ragcore.config.settings import Settings

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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Construct the container once, and release it on shutdown.

        Configuration is validated here, so a malformed setting is a container that does not
        start rather than a ``None`` surfacing on whichever endpoint is hit first
        (research R-019).

        **Cancellation-safe.** Shutdown work belongs after the ``yield``, where Starlette runs it
        during a controlled shutdown. Nothing here catches :class:`asyncio.CancelledError`.
        """
        app.state.container = container if container is not None else build_container(settings)
        try:
            yield
        finally:
            app.state.container = None

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
    # identity is inside correlation and every request is correlated before anything refuses it.
    app.add_middleware(IdentityHeaderMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    install_problem_handlers(app)

    app.include_router(customer_router)
    app.include_router(staff_router)
    app.include_router(workload_router)

    return app
