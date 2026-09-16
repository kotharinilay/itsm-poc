"""The two probes Container Apps calls, and the only surface served without gateway provenance.

**Outside every audience prefix, deliberately.** These paths sit at ``/health/*`` rather than under
``/api/workload/v1`` because of where the caller is: the probe comes from the Container Apps
infrastructure, on the internal network, and does not traverse Front Door or APIM. It therefore
carries no bearer token, no ``X-Idp-*`` contract and no gateway client certificate, and it has
nothing it could carry instead.

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

from fastapi import APIRouter

from ragcore.api.schemas import HealthStatus

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
async def ready() -> HealthStatus:
    """Readiness. A replica failing this is taken out of rotation rather than restarted.

    Returns:
        ``ok`` when this replica should receive traffic.

    Note:
        The dependency checks this will consult — PostgreSQL, and the checkpointer's schema — land
        with the components that own them. Until then this reports process readiness only, which is
        honest: it never claims a dependency is healthy, it only declines to claim otherwise.
    """
    return HealthStatus()
