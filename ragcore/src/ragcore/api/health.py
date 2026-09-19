"""The two probes Container Apps calls, and the platform's only anonymous surface.

**Outside every audience prefix, deliberately.** These paths sit at ``/health/*`` rather than under
``/api/workload/v1`` because of where the caller is: the probe comes from the Container Apps
infrastructure, on the internal network, and does not traverse Front Door or APIM. It therefore
carries no bearer token and no ``X-Idp-*`` contract, and it has nothing it could carry instead.

A probe published inside an audience prefix would be a hole in the trust boundary shaped exactly
like the thing the boundary exists to prevent: a path under ``/api/`` that is routed publicly by
Front Door, validated by APIM, and yet must also answer an unauthenticated caller on the inside.
Moving it out removes the contradiction rather than documenting it.

**They answer different questions and must not be merged** — the same split the .NET side makes, at
the same paths, because an operator reading two dashboards should not have to remember which
deployable spells it differently. Liveness asks whether the process should be restarted; readiness
asks whether it should receive traffic. A liveness probe that checked PostgreSQL would restart every
replica when the database had a bad minute, turning a dependency blip into an outage.

Neither probe reveals anything about an organisation, a session or a decision (spec 13.6).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

from ragcore.api.schemas import HealthStatus

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.composition import Container

_log: Final = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"], include_in_schema=False)
"""Excluded from every published document.

There is no audience this belongs to, and :mod:`ragcore.api.openapi` splits documents by audience
prefix — so a probe in a document would have to be assigned to a surface it is not part of.
"""


@router.get("/live")
async def live() -> HealthStatus:
    """Liveness. Process-only, and it performs no dependency check.

    Returns:
        ``ok`` whenever the process is running and the ASGI pipeline is intact. That is the whole
        claim, and it is deliberately a claim nothing external can falsify.
    """
    return HealthStatus()


@router.get("/ready")
async def ready(request: Request) -> HealthStatus:
    """Readiness. A replica failing this is taken out of rotation rather than restarted.

    **Checks PostgreSQL, and only PostgreSQL.** The database is the single authority for durable
    state: a replica that cannot reach it can serve nothing, so taking it out of rotation is exactly
    right. Every other dependency is deliberately excluded, and each exclusion is a decision:

    * **The AI Gateway, the system of record, Graph, AI Search.** Unreachable means *degraded*, not
      *unable to serve*. The platform continues in reduced mode when an external system is
      unavailable (spec FR-EXT-020), and a readiness probe that checked them would convert a third
      party's outage into an outage of ours — every replica out of rotation, nothing serving, and
      the cause in somebody else's datacentre.
    * **Redis.** Transient by definition. A cache miss is the normal path.
    * **Service Bus.** The API publishes through the outbox, which is a PostgreSQL write.
      Publication is the dispatcher's problem and is not in the request path.

    Returns:
        ``ok`` when this replica should receive traffic.

    Raises:
        HTTPException: 503 when the database cannot be reached. The body names the dependency and
            nothing else — no DSN, no driver message, no stack. A probe response is one of the few
            things served anonymously, so what it may disclose is narrow by construction
            (spec 13.6).
    """
    container: Container | None = getattr(request.app.state, "container", None)

    if container is None or container.engine is None:
        # No engine means the process has not finished starting, or was built without one. Not ready
        # is the honest answer; claiming otherwise would put a replica into rotation that has
        # nothing to serve with.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This replica is not ready: the platform database is not configured.",
        )

    try:
        async with container.engine.connect() as connection:
            # `SELECT 1` rather than a table read: readiness asks whether the connection pool can
            # reach the server, and a query touching a table would also fail on a permission or
            # migration problem that a restart cannot fix and that rotation should not hide.
            await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — every failure mode has the same answer: not ready
        _log.warning("Readiness check failed: the platform database is unreachable.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This replica is not ready: the platform database is unreachable.",
        ) from None

    return HealthStatus()
