"""Identity, derived once at the Gateway and consumed — never parsed, never accepted.

**No token parsing.** Identity is derived exactly once, at APIM, and both deployables consume the
same closed header contract (constitution Principle I). This middleware reads those headers and
nothing else. There is no JWT library imported here and no public key to rotate, because there is
no token to validate at this tier.

**Any request supplying tenant or role is rejected outright** (spec FR-IDENT-002). Not ignored —
*rejected*. The distinction matters: silently ignoring a ``tenant_id`` query parameter leaves a
caller believing it worked, and leaves the next reader of the code unsure whether some path
honours it. A 400 makes the contract unambiguous and makes an attempt visible in the logs.

The rejection list covers headers, query parameters and path segments, because the same claim can
be made in all three and only one of them needs to be missed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragcore.api.middleware.problems import problem_response
from ragcore.domain.principal import IDENTITY_HEADERS

FORBIDDEN_CLIENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "tenant",
        "tenantid",
        "tenant_id",
        "tenant-id",
        "organisation",
        "organization",
        "orgid",
        "org_id",
        "org-id",
        "role",
        "roles",
        "staffrole",
        "staff_role",
        "staff-role",
        "audience",
        "aud",
        "principal",
        "principalid",
        "principal_id",
        "oid",
        "actas",
        "act_as",
        "act-as",
        "onbehalfof",
        "on_behalf_of",
        "impersonate",
    }
)
"""Names a client MUST NOT supply, in any position.

Compared case-insensitively with separators stripped, so ``X-Tenant-Id``, ``tenant_id`` and
``tenantId`` are one entry rather than three that somebody has to remember to add.

``tenantId`` as a **staff read filter** is separate and legitimate (contracts/README.md): it
narrows within the set a caller may already see and is handled by the .NET read side, which this
middleware does not front.
"""

_GATEWAY_HEADERS: Final[frozenset[bytes]] = frozenset(
    header.lower().encode("latin-1") for header in IDENTITY_HEADERS
)


def _is_forbidden(name: str) -> bool:
    """Whether ``name`` is a client claim of authority, in any spelling.

    Folds case and separators, then checks the name both as written and with a leading ``x``
    removed. The ``X-`` prefix is the conventional shape for a custom header, so ``X-Tenant-Id``,
    ``x-roles`` and ``tenant_id`` all have to land on the same entry — otherwise the list has to
    carry a prefixed and an unprefixed spelling of everything, and the one somebody forgets to
    add is the one that gets through.
    """
    folded = name.lower().replace("-", "").replace("_", "")
    return folded in FORBIDDEN_CLIENT_FIELDS or folded.removeprefix("x") in FORBIDDEN_CLIENT_FIELDS


class IdentityHeaderMiddleware:
    """Reject self-asserted authority, then let the request through.

    Pure ASGI rather than ``BaseHTTPMiddleware``: the latter wraps the request in an anyio task
    group that changes how cancellation propagates on client disconnect, and cancellation
    behaviour is something this platform commits to rather than tolerates.

    This middleware **establishes nothing**. It does not construct a
    :class:`~ragcore.domain.principal.AuthenticatedPrincipal` and does not resolve a tenant —
    admission is trusted identity *plus registry state*, the registry is an async port, and
    reaching it from middleware would put an I/O dependency on every request including the health
    check. :mod:`ragcore.api.deps` does that work, per route, through ``Depends``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Screen one request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        offender = _self_asserted_field(scope)
        if offender is not None:
            await _reject(scope, send, offender)
            return

        await self.app(scope, receive, send)


def _self_asserted_field(scope: Scope) -> str | None:
    """Return the first forbidden field a client supplied, or ``None``.

    Gateway-derived headers are exempt by name: APIM sets them, and APIM is upstream of anything
    a client can reach. A client that sets one directly is not a case this middleware can
    distinguish — the Gateway strips and re-sets them, which is where that boundary belongs.
    """
    headers: Iterable[tuple[bytes, bytes]] = scope.get("headers", [])
    for raw_name, _ in headers:
        if raw_name.lower() in _GATEWAY_HEADERS:
            continue
        name = raw_name.decode("latin-1")
        if _is_forbidden(name):
            return name

    raw_query: bytes = scope.get("query_string", b"")
    for pair in raw_query.decode("latin-1").split("&"):
        if not pair:
            continue
        parameter = pair.split("=", 1)[0]
        if _is_forbidden(parameter):
            return parameter

    return None


async def _reject(scope: Scope, send: Send, offender: str) -> None:
    """Refuse the request with problem details, naming the field but echoing no value."""
    message: Message
    response = problem_response(
        status=400,
        title="Self-asserted authority",
        detail=(
            f"'{offender}' MUST NOT be supplied by a client. Organisation, roles and audience are "
            "derived from trusted identity at the Gateway and are never request parameters."
        ),
        instance=scope.get("path", ""),
        correlation_id=_correlation_of(scope),
    )
    for message in response:
        await send(message)


def _correlation_of(scope: Scope) -> str:
    """The correlation identifier bound by the correlation middleware, if it ran first."""
    state = scope.get("state")
    if isinstance(state, dict):
        value = state.get("correlation_id")
        if isinstance(value, str):
            return value
    return ""
