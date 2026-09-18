"""Health. **Liveness is the process; readiness is the platform — never a customer system.**

`/health/live` is process-only with no dependency checks. `/health/ready` covers **platform**
dependencies: the durable store, the message transport and the secret store.

**Readiness MUST NOT depend on an external customer system** (`FR-INTEG-026`, constitution
§Health). A ServiceNow, Graph or MCP-server outage is an operational condition to be reported and
degraded around, never an unready replica. A probe that failed on one would remove capacity at
exactly the moment the fallback path needs it — and because readiness drives scaling, one customer's
outage would scale the platform toward zero for every other customer. That is the noisy-neighbour
failure the isolation rules exist to prevent, arriving through the back door.

**Neither endpoint discloses anything.** No identity, no organisation data, no dependency name, no
configuration. A failing readiness check reports *that* it failed, not *what* failed; the detail
goes to telemetry, correlated. An unauthenticated probe that named its dependencies would be a
reconnaissance surface on a service whose dependency list includes a vault.

**Probes register with their own tasks.** This module owns the contract and the endpoint; the
concrete durable-store, message-transport and secret-store probes are registered by the composition
root as those subsystems land. A service with no registered probes reports ready, which is correct
for a process that genuinely has nothing to wait for — and becomes wrong the moment a dependency
exists, which is why registration is the subsystem's obligation rather than this module's.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi import APIRouter, Response, status

from integrations.api.middleware.correlation import current_correlation_id

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Sequence

__all__ = ["ReadinessProbe", "ReadinessRegistry", "build_health_router"]

logger = logging.getLogger(__name__)


@runtime_checkable
class ReadinessProbe(Protocol):
    """A platform dependency that must be reachable before this replica takes traffic.

    **Implemented only for platform dependencies.** An implementation that reached a customer
    system would be a defect, and the review question is simply: *would a customer's outage make
    this return False?* If yes, it does not belong here.
    """

    @property
    def name(self) -> str:
        """The dependency's name, for telemetry only — **never for a response body**."""
        ...

    async def check(self) -> bool:
        """Whether the dependency is reachable.

        Returns:
            ``True`` when ready. An implementation returns ``False`` or raises; both are treated
            as not-ready, because "I could not reach it" and "it told me no" have the same
            consequence for whether this replica should take traffic.
        """
        ...


class ReadinessRegistry:
    """The probes this process waits on.

    Held by the composition root. Empty is a valid state and means "nothing to wait for" — not
    "checks disabled".
    """

    def __init__(self, probes: Sequence[ReadinessProbe] | None = None) -> None:
        """Bind the registry to its probes.

        Args:
            probes: The platform dependency probes. Registered by the composition root as each
                subsystem is bound.
        """
        self._probes: list[ReadinessProbe] = list(probes or ())

    def register(self, probe: ReadinessProbe) -> None:
        """Add a probe.

        Args:
            probe: The platform dependency probe.
        """
        self._probes.append(probe)

    async def all_ready(self) -> bool:
        """Whether every registered probe reports ready.

        Probes run concurrently: readiness is on the scaling path, and checking three dependencies
        serially turns three timeouts into one long one.

        Returns:
            ``True`` when every probe succeeded, or when none is registered.
        """
        if not self._probes:
            return True

        async def _safe(probe: ReadinessProbe) -> bool:
            try:
                return await probe.check()
            except Exception:
                # Logged with the dependency name; the name does NOT reach the response body.
                logger.warning(
                    "Readiness probe %s failed",
                    probe.name,
                    exc_info=True,
                    extra={"correlationId": current_correlation_id()},
                )
                return False

        results = await asyncio.gather(*(_safe(p) for p in self._probes))
        return all(results)


def build_health_router(registry: ReadinessRegistry) -> APIRouter:
    """Build the health router.

    Args:
        registry: The readiness probes for this process.

    Returns:
        A router exposing `/health/live` and `/health/ready`.
    """
    router = APIRouter(tags=["health"], include_in_schema=False)

    @router.get("/health/live")
    async def live() -> Response:
        """Liveness: the process is running. **No dependency is consulted.**

        A liveness probe that checked a dependency would restart a healthy process because
        something else was down, turning one outage into two.
        """
        return Response(status_code=status.HTTP_200_OK)

    @router.get("/health/ready")
    async def ready() -> Response:
        """Readiness: every **platform** dependency is reachable.

        Returns 200 or 503 with an empty body. The body is empty deliberately — a failing probe
        names its dependency in telemetry, not to an unauthenticated caller.
        """
        if await registry.all_ready():
            return Response(status_code=status.HTTP_200_OK)
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    return router
