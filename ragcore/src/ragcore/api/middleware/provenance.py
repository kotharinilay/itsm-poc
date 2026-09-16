"""Gateway provenance — the control that makes the identity contract evidence rather than input.

Everything else in this package consumes ``X-Idp-*`` as trusted. This module is why it may.

**The gap this closes.** Until this middleware existed, the identity middleware exempted the five
gateway headers by name and said so in its own comments: *"A client that sets one directly is not a
case this middleware can distinguish."* The whole model therefore rested on network reachability —
internal ingress, a private VNet — which the specification is explicit is **not sufficient alone**
(spec 10.3). A VNet admits everything already inside it: a compromised sidecar, a misconfigured job,
a second container app. Any of those could have minted any tenant and any role it liked.

**How provenance is proved.** APIM presents a client certificate on the backend connection.
Container Apps ingress validates it and republishes it as ``X-Forwarded-Client-Cert`` — *ingress
sets that header itself*, replacing whatever arrived, which is precisely what makes the hash in it
evidence and not merely another thing a caller typed. This middleware compares that hash against a
configured allow-list. APIM also deletes any inbound copy of the header before forwarding, so the
two ends agree without either trusting the other's diligence.

**A hash, not a shared secret.** The allow-list holds SHA-256 hashes of a public certificate.
Knowing one buys nothing, so it is ordinary configuration rather than Key Vault material — and
treating it as a secret would wrongly suggest that keeping it quiet was load-bearing.

**Refusal, not sanitisation.** A request that cannot prove provenance is rejected whole. Stripping
the ``X-Idp-*`` headers and continuing would hand an attacker a ``200`` for a probe and leave the
attempt indistinguishable, in the logs, from an ordinary unauthenticated call.

The single authoritative description of all of this is ``build/policy/edge-trust.json``, which this
module and its .NET counterpart both enforce and which the security tests read directly.
"""

from __future__ import annotations

from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragcore.api.middleware.problems import problem_response

FORWARDED_CLIENT_CERT_HEADER: Final = "X-Forwarded-Client-Cert"
"""Set by Container Apps ingress from the certificate it validated. Never by a caller."""

_HEADER_BYTES: Final = FORWARDED_CLIENT_CERT_HEADER.lower().encode("latin-1")

HASH_ELEMENT: Final = "hash"
"""The XFCC element carrying the SHA-256 of the peer certificate, as lowercase hex."""

PROBLEM_TYPE: Final = "gateway-provenance-required"

EXEMPT_PATH_PREFIXES: Final[tuple[str, ...]] = ("/health",)
"""The only paths served without provenance, and the only ones that could be.

Health probes originate from the Container Apps infrastructure on the internal network. They do not
traverse APIM, carry no certificate, and have nothing they could carry instead. They are also the
sole anonymous surface (spec 13.6) and expose no identity, so a request that reaches one has gained
nothing.

A *prefix* rather than a list of exact paths, on purpose: an exact list grows an entry at a time,
and the entry somebody adds without thinking is the one that matters. Extending this requires
moving a route under ``/health``, which is visible in review. It is kept in step with
``build/policy/edge-trust.json`` by ``tests/security/test_edge_trust_policy.py``.
"""


class GatewayProvenanceUnconfiguredError(RuntimeError):
    """Raised at construction when no gateway certificate hash is configured.

    **Fail closed, at startup, with no environment branch.** The alternative is a process that
    starts happily and accepts forged identity — a defect that produces no error, no failed probe
    and no unusual log line, and looks exactly like a service working correctly.

    That makes this stricter than the Key Vault setting next door, which is legitimately absent on a
    developer machine. The difference is the failure mode, not the ceremony: an unconfigured vault
    fails loudly on the first secret it needs.
    """


def _normalise(thumbprint: str) -> str:
    """Fold one configured or forwarded hash to its comparison form."""
    return thumbprint.strip().strip('"').replace(":", "").lower()


def parse_thumbprints(configured: str) -> frozenset[str]:
    """Parse the configured allow-list.

    Comma-separated because rotation is an **overlap**: the outgoing and incoming hashes sit here
    together while APIM is cut over, so there is no instant at which neither is accepted. A single
    value would make every rotation a synchronised swap with a window in which the platform is down
    or, worse, briefly unguarded.

    Args:
        configured: The raw setting value.

    Returns:
        The accepted hashes, folded for comparison. Empty when nothing is configured — the caller
        decides that this is fatal, so that the parsing rule and the startup rule stay separable.
    """
    return frozenset(
        normalised for entry in configured.split(",") if (normalised := _normalise(entry))
    )


def require_thumbprints(configured: str) -> frozenset[str]:
    """Parse the allow-list, refusing an empty one.

    **Called eagerly by the composition root, not lazily by the middleware.** Starlette builds its
    middleware stack on first use, so a check that lived only in the middleware constructor would
    fail when the application *started serving* rather than when it was *built* — and the gap
    between those two moments is where a process can look healthy. Raising here makes an
    unconfigured deployment a container that never starts.

    Args:
        configured: The raw setting value.

    Returns:
        The accepted hashes.

    Raises:
        GatewayProvenanceUnconfiguredError: When nothing is configured.
    """
    accepted = parse_thumbprints(configured)

    if not accepted:
        raise GatewayProvenanceUnconfiguredError(
            "No gateway certificate hash is configured, so this process cannot distinguish a "
            "request that came through APIM from one that did not. Set "
            "SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS. Refusing to start: serving without "
            "this control would accept forged identity headers and look healthy doing it."
        )

    return accepted


def forwarded_certificate_hash(header_value: str) -> str | None:
    """Extract the peer certificate hash from one ``X-Forwarded-Client-Cert`` value.

    The header is ``Key=Value;Key=Value`` per element, with ``,`` separating elements when a chain
    is forwarded. Container Apps ingress sets **exactly one** element, for the peer it validated.

    **More than one element is refused rather than resolved.** A chain here means something between
    APIM and this process appended to the header, and there is no reading of that which is both safe
    and knowable from inside this function: taking the first trusts whatever was furthest away,
    taking the last trusts whatever was nearest, and either choice is a policy decision made by a
    parser. Refusing states the deployment has changed.

    Args:
        header_value: The raw header.

    Returns:
        The hash, folded for comparison, or ``None`` when the header carries no single usable one.
    """
    if header_value.count(",") > 0:
        return None

    for element in header_value.split(";"):
        key, separator, value = element.partition("=")
        if separator and key.strip().lower() == HASH_ELEMENT:
            folded = _normalise(value)
            return folded or None

    return None


class GatewayProvenanceMiddleware:
    """Refuse any request that cannot prove it arrived through APIM.

    Runs **outside** the identity middleware and inside correlation, so that a refusal is
    correlatable and so that no self-asserted-authority screening, route match or dependency ever
    runs for a caller that did not come through the gateway.

    Pure ASGI rather than ``BaseHTTPMiddleware``, for the same reason as its neighbours: the latter
    wraps the request in an anyio task group that changes how cancellation propagates on client
    disconnect, and cancellation behaviour is something this platform commits to rather than
    tolerates.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        accepted_thumbprints: frozenset[str],
        exempt_path_prefixes: tuple[str, ...] = EXEMPT_PATH_PREFIXES,
    ) -> None:
        """Bind the allow-list for the life of the process.

        Args:
            app: The next ASGI application.
            accepted_thumbprints: SHA-256 hashes of the gateway client certificates to accept.
            exempt_path_prefixes: Paths served without provenance. Defaults to the health prefix,
                and a caller overriding it is doing so in a test.

        Raises:
            GatewayProvenanceUnconfiguredError: When the allow-list is empty. See the class
                docstring on :class:`GatewayProvenanceUnconfiguredError` for why this is fatal
                rather than permissive.
        """
        if not accepted_thumbprints:
            raise GatewayProvenanceUnconfiguredError(
                "No gateway certificate hash is configured, so this process cannot distinguish a "
                "request that came through APIM from one that did not. Set "
                "SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS. Refusing to start: serving without "
                "this control would accept forged identity headers and look healthy doing it."
            )

        self.app = app
        self._accepted = accepted_thumbprints
        self._exempt = exempt_path_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Screen one request for gateway provenance."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._is_exempt(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        if not self._has_provenance(scope):
            await _refuse(scope, send)
            return

        await self.app(scope, receive, send)

    def _is_exempt(self, path: str) -> bool:
        """Whether this path is served without provenance.

        Matched on a path segment boundary, not a bare prefix: ``/healthcheck-bypass`` must not
        inherit the exemption granted to ``/health``.
        """
        return any(path == prefix or path.startswith(prefix + "/") for prefix in self._exempt)

    def _has_provenance(self, scope: Scope) -> bool:
        """Whether this request carries a forwarded certificate hash this process accepts."""
        values = [
            value.decode("latin-1", errors="replace")
            for name, value in scope.get("headers", [])
            if name.lower() == _HEADER_BYTES
        ]

        # Exactly one. Zero means no certificate was validated; more than one means two parties
        # both claimed to have validated something, and this process cannot know which to believe.
        if len(values) != 1:
            return False

        forwarded = forwarded_certificate_hash(values[0])
        return forwarded is not None and forwarded in self._accepted


async def _refuse(scope: Scope, send: Send) -> None:
    """Refuse with problem details that describe the rule and disclose no part of the control.

    403 rather than 401: the request is not missing a credential it could supply, it arrived by a
    path that is not served. Naming the certificate, the allow-list or which of the two checks
    failed would describe the boundary to whoever is probing it.
    """
    message: Message
    response = problem_response(
        status=403,
        title="Gateway provenance required",
        detail=(
            "This API is served only through the platform gateway. Identity is derived once, at "
            "the gateway, and a request that did not arrive through it carries no identity this "
            "service can accept."
        ),
        instance=scope.get("path", ""),
        correlation_id=_correlation_of(scope),
        problem_type=PROBLEM_TYPE,
    )
    for message in response:
        await send(message)


def _correlation_of(scope: Scope) -> str:
    """The correlation identifier bound by the correlation middleware, running outside this one."""
    state = scope.get("state")
    if isinstance(state, dict):
        value = state.get("correlation_id")
        if isinstance(value, str):
            return value
    return ""
