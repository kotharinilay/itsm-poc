"""Gateway provenance. **Refused, not sanitised.**

Runs **before** identity. It proves the request actually came through APIM by validating the
certificate hash Container Apps ingress forwarded against a required allow-list.

**The header is `X-Forwarded-Client-Cert`, and it is not ours to choose.**
`build/policy/edge-trust.json` names it as the platform's `provenanceHeader`, and
`ragcore/src/ragcore/api/middleware/provenance.py` reads the same one. APIM presents a client
certificate, ingress validates it and republishes it here — *ingress sets the header itself*,
replacing whatever arrived, which is precisely what makes the hash in it evidence rather than input.
Two stacks reading two different headers would be two controls that drift, which is the failure the
single policy registry exists to prevent.

**Why refusal rather than stripping the header and continuing.** Stripping returns *success* to an
attacker and leaves the attempt indistinguishable from an ordinary unauthenticated call — so the one
event worth alerting on becomes the one event nobody can see. `SC-DEMO-003b` measures this: a
request carrying a well-formed but **self-supplied** identity contract is the shape a real bypass
takes, and it must fail.

**Why an empty allow-list stops the process at startup.** Not because it would fail open — this
middleware fails *closed* on an empty set, refusing everything. Two reasons that are actually true:

* **It converts a silent total outage into a loud deployment failure.** Health probes are exempt
  from provenance, so a service with an empty allow-list refuses every request while every replica
  reports healthy. That is the same misleading outage `build/infra/monitoring/` alerts on for
  certificate expiry, arriving at deploy time instead.
* **It removes the fail-open refactor before anyone can write it.** The tempting fix when this bites
  in local development is one word — `if self._accepted and presented not in ...` — which reads as
  "only enforce when configured" and *is* fail-open. Making the empty set unconstructable
  (:class:`~integrations.config.settings.EdgeTrustSettings`) leaves that change nowhere to start.

Health endpoints are exempt, because a platform probe originates inside the environment, does not
traverse APIM, and has no certificate it could carry instead. That exemption is why certificate
expiry is a **misleading** outage — replicas stay green while serving nothing — and it is alerted on
separately.
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

__all__ = [
    "FORWARDED_CLIENT_CERT_HEADER",
    "HASH_ELEMENT",
    "ProvenanceMiddleware",
    "forwarded_certificate_hash",
    "normalise_thumbprint",
]

FORWARDED_CLIENT_CERT_HEADER: Final = "X-Forwarded-Client-Cert"
"""Set by Container Apps ingress for the peer certificate it validated. Never by a caller."""

HASH_ELEMENT: Final = "hash"
"""The XFCC element carrying the SHA-256 of the peer certificate, as lowercase hex."""

# Platform probes reach the container directly and never traverse APIM, so they cannot carry
# provenance. Exempting them keeps a healthy replica reporting healthy; it widens no API surface,
# because neither path returns identity, tenant data or configuration.
_EXEMPT_PATH_PREFIXES: Final[tuple[str, ...]] = ("/health",)


def normalise_thumbprint(thumbprint: str) -> str:
    """Fold one configured or forwarded hash to its comparison form.

    Args:
        thumbprint: The raw value, possibly quoted, colon-separated or mixed case.

    Returns:
        The folded value. Comparison happens on folded values at both ends so that a certificate
        exported in one tool's formatting still matches one configured from another's.
    """
    return thumbprint.strip().strip('"').replace(":", "").lower()


def forwarded_certificate_hash(header_value: str) -> str | None:
    """Extract the peer certificate hash from one `X-Forwarded-Client-Cert` value.

    The header is `Key=Value;Key=Value` per element, with `,` separating elements when a chain is
    forwarded. Container Apps ingress sets **exactly one** element, for the peer it validated.

    **More than one element is refused rather than resolved.** A chain here means something between
    APIM and this process appended to the header, and there is no reading of that which is both safe
    and knowable from inside this function: taking the first trusts whatever was furthest away,
    taking the last trusts whatever was nearest, and either choice is a policy decision made by a
    parser. Refusing states that the deployment has changed.

    Args:
        header_value: The raw header.

    Returns:
        The folded hash, or ``None`` when the header carries no single usable one.
    """
    if header_value.count(",") > 0:
        return None

    for element in header_value.split(";"):
        key, separator, value = element.partition("=")
        if separator and key.strip().lower() == HASH_ELEMENT:
            folded = normalise_thumbprint(value)
            return folded or None

    return None


class ProvenanceMiddleware(BaseHTTPMiddleware):
    """Refuses any request that did not arrive through the gateway."""

    def __init__(self, app: object, edge_trust: EdgeTrustSettings) -> None:
        """Bind the middleware to its allow-list.

        Args:
            app: The ASGI application.
            edge_trust: The accepted certificate hashes, already proven non-empty at startup and
                folded here once rather than on every request.
        """
        super().__init__(app)  # type: ignore[arg-type]
        self._accepted = frozenset(
            normalise_thumbprint(t) for t in edge_trust.gateway_certificate_thumbprints
        )

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
        if request.url.path.startswith(_EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        presented = forwarded_certificate_hash(
            request.headers.get(FORWARDED_CLIENT_CERT_HEADER, "")
        )

        if presented is None or presented not in self._accepted:
            return problem(
                status=403,
                title="Forbidden",
                detail="This API is reachable only through the gateway.",
                kind="gateway-provenance-required",
                instance=request.url.path,
            )

        return await call_next(request)
