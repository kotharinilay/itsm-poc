"""The API shell. **FastAPI owns transport; it owns no business policy.**

Constitution §FastAPI architecture: endpoints contain no business policy, dependencies establish the
request context, and authorization decisions live in application and domain policy.

**Middleware order is load-bearing** and is the constitution's, not a preference:

```text
exception handling → correlation → trace context → identity → endpoint
```

Starlette applies middleware in reverse registration order, so the registrations below read
bottom-up relative to that list. Two orderings in particular are the control rather than the style:

* **Correlation before anything that logs.** Otherwise the first record of a request — the one
  describing a request nobody can then find — is uncorrelated.
* **Identity last.** It rejects self-asserted authority before routing, so no endpoint and no
  dependency ever sees a client-supplied tenant or role.

**There is no backend-side provenance layer.** The certificate-based one that used to sit before
identity is **deferred** (ADR 0008) and no replacement was introduced, so this service cannot
itself prove a request arrived through APIM. Internal-only ingress and APIM's deletion of every
inbound copy of the contract are what remain; both are recorded, with their limits, in the ADR.

**This service is not client-facing.** It serves the workload audience only; only RagCore calls
it, through APIM. It emits its own OpenAPI document, never merged with RagCore's — a merged one
would let a customer-facing client discover this surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from integrations.api.health import build_health_router
from integrations.api.middleware.correlation import CorrelationMiddleware
from integrations.api.middleware.identity import IdentityMiddleware
from integrations.api.middleware.problems import ProblemMiddleware, install_exception_handlers
from integrations.api.workload.routes import build_workload_router
from integrations.config.composition import build_container

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.config.composition import Container

__all__ = ["create_app"]

_DESCRIPTION = (
    "The Synthia Integrations Service. Owns the tool catalogue, the connector registry and all "
    "traffic to external systems. Reached only by RagCore, on the workload audience, through APIM."
)


def create_app(container: Container | None = None) -> FastAPI:
    """Build the application.

    Args:
        container: A pre-built container. Supplied by tests so they can bind a validated
            configuration without reaching Azure; built here otherwise, which is what makes
            invalid configuration fail at process start.

    Returns:
        The configured application.
    """
    resolved = container or build_container()

    app = FastAPI(
        title="Synthia Integrations API",
        # `v1`, matching the URI segment, NOT an assembly version. The published version is the one
        # a client is pinned to; an assembly version moves on a patch release that changes no route,
        # which would tell every client their contract had changed when it had not.
        version="v1",
        description=_DESCRIPTION,
        # One document per audience per deployable; never merged with RagCore's.
        openapi_url="/api/workload/v1/integrations/openapi.json",
        docs_url=None,
        redoc_url=None,
    )
    app.state.container = resolved

    # Before the routers, so a framework-raised 422 is already the platform's one error contract by
    # the time the document is generated from the routes.
    install_exception_handlers(app)

    # Registered in reverse of execution order — Starlette wraps each around the previous, so the
    # LAST registered runs FIRST. Reading bottom-up gives the constitution's order.
    app.add_middleware(IdentityMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(ProblemMiddleware)

    app.include_router(build_health_router(resolved.readiness))
    app.include_router(build_workload_router(resolved))

    return app
