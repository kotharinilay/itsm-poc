"""The workload principal. **No token parsing, and the token's tenant is not the customer's.**

Identity is derived exactly once, at APIM (A1 §4.5). This service consumes only the
closed `X-Idp-*` contract APIM writes and **MUST NOT parse an access token** — there is no JWT
library here and adding one is an architectural change, not a convenience.

**The workload tenant is the Operator tenant, never a customer's.** `X-Idp-Tenant-Id` on this
audience is the Entra provenance of the service principal that called. It is auditable information
about *who called*, and it is **never** the organisation acted upon. That organisation comes from
durable state — the integration job row on the asynchronous path, the durable object an opaque
identifier names on the synchronous path (`FR-INTEG-018`).

This module therefore deliberately offers **no** way to obtain a customer tenant. A caller holding
a principal and wanting one has nowhere to go from here, which is the intended outcome: the type
system is where "tenant context MUST NEVER be accepted from an untrusted client field" stops being
a rule someone has to remember.

**App-only, never delegated.** APIM refuses a delegated token on this audience before the request
arrives; this module re-asserts the credential class so a misconfigured policy cannot present a
human's authority as a machine's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from starlette.middleware.base import BaseHTTPMiddleware

from integrations.api.middleware.problems import problem

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["IdentityMiddleware", "WorkloadPrincipal", "current_principal"]

_TENANT_HEADER: Final = "X-Idp-Tenant-Id"
_PRINCIPAL_HEADER: Final = "X-Idp-Principal-Id"
_CREDENTIAL_CLASS_HEADER: Final = "X-Idp-Credential-Class"
_SURFACE_HEADER: Final = "X-Idp-Client-Surface"

_EXEMPT_PATHS: Final = frozenset({"/health/live", "/health/ready", "/health/startup"})

_FORBIDDEN_CLIENT_FIELDS: Final = frozenset(
    {
        "tenant",
        "tenantid",
        "organisation",
        "organization",
        "orgid",
        "role",
        "roles",
        "staffrole",
        "audience",
        "aud",
        "principal",
        "principalid",
        "oid",
        "actas",
        "onbehalfof",
        "impersonate",
    }
)
"""Names a client MUST NOT supply. The same set RagCore's identity middleware refuses, compared the
same way — case-insensitively, separators stripped, an ``X-`` prefix ignored — so ``tenantId``,
``tenant_id`` and ``X-Tenant-Id`` are one entry. Restated rather than imported: the two services
share no package (ADR-0007)."""


def _is_forbidden(name: str) -> bool:
    folded = name.lower().replace("-", "").replace("_", "")
    return (
        folded in _FORBIDDEN_CLIENT_FIELDS or folded.removeprefix("x") in _FORBIDDEN_CLIENT_FIELDS
    )


_REQUEST_STATE_KEY: Final = "workload_principal"


@dataclass(frozen=True, slots=True)
class WorkloadPrincipal:
    """The non-human caller, as APIM derived it.

    Attributes:
        principal_id: The calling service principal's object id. A machine identity, never a human
            one.
        operator_tenant_id: The Entra tenant the credential was issued in — **the Operator tenant**.
            Carried for audit because the caller's own provenance is auditable information. It is
            **not** the organisation being acted upon and there is no accessor here that pretends
            otherwise.
    """

    principal_id: str
    operator_tenant_id: str


def current_principal(request: Request) -> WorkloadPrincipal:
    """The principal established for this request.

    Args:
        request: The inbound request.

    Returns:
        The workload principal.

    Raises:
        LookupError: When no principal was established. A **platform defect** rather than a
            user-facing condition: the middleware refuses anonymous requests before any endpoint
            runs, so reaching an endpoint without one means the pipeline is misassembled. Raised
            rather than returning ``None`` so it cannot be quietly treated as "no caller".
    """
    principal = getattr(request.state, _REQUEST_STATE_KEY, None)
    if principal is None:
        raise LookupError(
            "no workload principal on the request. Identity middleware did not run, which is a "
            "composition defect rather than an authorization outcome."
        )
    return principal  # type: ignore[no-any-return]


class IdentityMiddleware(BaseHTTPMiddleware):
    """Reads the closed header contract and establishes the workload principal."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Establish the principal, or refuse.

        Args:
            request: The inbound request.
            call_next: The rest of the pipeline.

        Returns:
            The response, or a problem when the contract is absent or not app-only.
        """
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # REFUSED, NOT IGNORED. A client-supplied organisation, role or audience establishes no
        # authority here — the organisation comes from durable state — and it used to be silently
        # dropped. RagCore and the monolith refuse the same request with a 400, and a boundary
        # that quietly tolerates the attempt is one where nobody can tell an attempt happened.
        for name in request.query_params:
            if _is_forbidden(name):
                return problem(
                    status=400,
                    title="Self-asserted authority",
                    detail=(
                        f"'{name}' MUST NOT be supplied by a client. The organisation is recovered "
                        "from the durable object an identifier names, never from a request field."
                    ),
                    kind="self-asserted-authority",
                    instance=request.url.path,
                )

        principal_id = request.headers.get(_PRINCIPAL_HEADER, "")
        operator_tenant_id = request.headers.get(_TENANT_HEADER, "")
        credential_class = request.headers.get(_CREDENTIAL_CLASS_HEADER, "")
        surface = request.headers.get(_SURFACE_HEADER, "")

        if not principal_id or not operator_tenant_id:
            return problem(
                status=401,
                title="Unauthenticated",
                detail="The request carried no usable identity.",
                kind="unauthenticated",
                instance=request.url.path,
            )

        # APIM already refuses a delegated token on this audience. This is the second half of that
        # check, and it is not redundant: a policy misconfiguration is exactly the failure that
        # would let a human's authority arrive here wearing a machine's shape, and it would appear
        # in the audit record as a machine.
        if credential_class != "app" or surface != "workload":
            return problem(
                status=403,
                title="Forbidden",
                detail="This audience accepts only an application credential.",
                kind="forbidden",
                instance=request.url.path,
            )

        request.state.workload_principal = WorkloadPrincipal(
            principal_id=principal_id,
            operator_tenant_id=operator_tenant_id,
        )
        return await call_next(request)
