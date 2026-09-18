"""Gateway provenance. **Refused, not sanitised.**

Runs **before** identity. It proves the request actually came through APIM by validating the
ingress-forwarded client-certificate hash against a required allow-list.

**Why refusal rather than stripping the headers and continuing.** Stripping returns *success* to
an attacker and leaves the attempt indistinguishable from an ordinary unauthenticated call — so
the one event worth alerting on becomes the one event nobody can see. `SC-DEMO-003b` measures
this: a request carrying a well-formed but **self-supplied** identity contract is the shape a real
bypass takes, and it must fail.

**The allow-list cannot be empty.** :class:`~integrations.config.settings.EdgeTrustSettings`
refuses to construct with an empty set, so the process does not start. An unconfigured vault fails
loudly; an unconfigured allow-list fails *silently by accepting forged identity*, which is the
asymmetry
that decides where the check belongs.

Health endpoints are exempt, because a platform probe does not traverse APIM. That exemption is the
reason certificate expiry is a **misleading** outage — replicas stay green while serving nothing —
and it is alerted on separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from starlette.middleware.base import BaseHTTPMiddleware

from integrations.api.middleware.problems import problem

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

    from integrations.config.settings import EdgeTrustSettings

__all__ = ["CERTIFICATE_HEADER", "ProvenanceMiddleware"]

CERTIFICATE_HEADER: Final = "X-Client-Certificate-Sha256"

# Platform probes reach the container directly and never traverse APIM, so they cannot carry
# gateway provenance. Exempting them is what keeps a healthy replica reporting healthy; it does not
# widen the API surface, because neither path returns identity, tenant data or configuration.
_EXEMPT_PATHS: Final = frozenset({"/health/live", "/health/ready", "/health/startup"})


class ProvenanceMiddleware(BaseHTTPMiddleware):
    """Refuses any request that did not arrive through the gateway."""

    def __init__(self, app: object, edge_trust: EdgeTrustSettings) -> None:
        """Bind the middleware to its allow-list.

        Args:
            app: The ASGI application.
            edge_trust: The accepted certificate hashes. Already proven non-empty at startup.
        """
        super().__init__(app)  # type: ignore[arg-type]
        self._accepted = edge_trust.gateway_certificate_thumbprints

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Validate provenance, or refuse.

        Args:
            request: The inbound request.
            call_next: The rest of the pipeline.

        Returns:
            The response, or a 403 problem when provenance cannot be proven.
        """
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        presented = request.headers.get(CERTIFICATE_HEADER, "")
        if presented.lower() not in {t.lower() for t in self._accepted}:
            return problem(
                status=403,
                title="Forbidden",
                detail="This API is reachable only through the gateway.",
                kind="gateway-provenance-required",
                instance=request.url.path,
            )

        return await call_next(request)
