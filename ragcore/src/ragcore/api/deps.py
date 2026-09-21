"""Dependency injection at the HTTP boundary, and nowhere else.

**Explicit dependency injection, with FastAPI ``Depends`` at HTTP boundaries**
(.claude/rules/10-principles.md P-26). Everything below resolves from the container built in
:mod:`ragcore.config.composition`; nothing here constructs an adapter, and no module deeper than
this one calls ``Depends`` at all. Application services take their collaborators as constructor
or function arguments and stay testable without a web framework.

**Service Locator is prohibited**, and the shape enforces it. The container is reached through
``request.app.state`` — set once at startup — rather than through a module-level global that any
code could import and query. A dependency not reachable from here is a dependency nothing should
be using.

**These dependencies establish context. They do not authorize.** They answer "who is calling and
on behalf of which admitted organisation". Whether that principal may do the thing is decided by
:mod:`ragcore.governance.gate` and :func:`ragcore.domain.roles.evaluate`, further in. Putting an
authorization check in a ``Depends`` would scatter policy across route decorators, where it is
invisible to the tests that prove it.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from ragcore.api.middleware.correlation import correlation_id_var
from ragcore.config.composition import Container
from ragcore.domain.identifiers import CorrelationId, EntraTenantId, PrincipalId
from ragcore.domain.principal import (
    IDENTITY_HEADERS,
    Audience,
    AuthenticatedPrincipal,
    CredentialClass,
    HumanIdentity,
)
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.tenancy import TenantContext
from ragcore.observability.context import bind_tenant


def get_container(request: Request) -> Container:
    """The composition root's container, bound to the application at startup.

    Raises:
        RuntimeError: When the lifespan handler did not run. A programming error rather than a
            request failure, and it fails loudly: a container assembled lazily on first request
            would move a configuration failure from startup to whichever endpoint was hit first.
    """
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, Container):
        raise RuntimeError(
            "no container on app.state; the lifespan handler did not run. Dependencies are "
            "constructed once at startup, never lazily per request."
        )
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_correlation_id() -> CorrelationId:
    """The identifier the correlation middleware bound for this request."""
    return CorrelationId(correlation_id_var.get())


CorrelationDep = Annotated[CorrelationId, Depends(get_correlation_id)]


def _header(request: Request, name: str) -> str:
    return request.headers.get(name, "").strip()


def _audience_for(path: str) -> Audience:
    """Derive the audience from the route the Gateway matched.

    **From the path, never from a request field** (spec FR-SURF-005). The surface decides which
    authorization model applies, and a person cannot promote themselves by anything they supply.

    Raises:
        HTTPException: 404 for a path on no known audience. Not 400: an unrecognised prefix is
            not a malformed request, it is a route that does not exist.
    """
    if path.startswith("/api/customer/"):
        return Audience.CUSTOMER
    if path.startswith("/api/staff/"):
        return Audience.STAFF
    if path.startswith("/api/workload/"):
        return Audience.WORKLOAD
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def get_principal(request: Request) -> AuthenticatedPrincipal:
    """Build the principal from the closed Gateway-derived header contract.

    **No token is parsed.** Identity is derived once, at APIM; this reads the result. The headers
    are the five in :data:`~ragcore.domain.principal.IDENTITY_HEADERS` and no others.

    Roles are read here but **not consulted here**. On a customer surface
    :attr:`~ragcore.domain.principal.AuthenticatedPrincipal.authorizable_roles` returns only
    ``end_user`` regardless of what arrived, so a staff member using a customer surface is an end
    user — enforced by the type rather than by each call site remembering.

    Raises:
        HTTPException: 401 when the contract is incomplete. Incomplete means the Gateway did not
            run or was bypassed, which is not a state to guess a default for.
    """
    tenant_raw = _header(request, "X-Idp-Tenant-Id")
    principal_raw = _header(request, "X-Idp-Principal-Id")
    if not tenant_raw or not principal_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Gateway-derived identity contract is incomplete.",
        )

    try:
        identity = HumanIdentity(
            tenant_id=EntraTenantId(UUID(tenant_raw)),
            principal_id=PrincipalId(UUID(principal_raw)),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Gateway-derived identity contract is malformed.",
        ) from exc

    return AuthenticatedPrincipal(
        identity=identity,
        roles=_roles(_header(request, "X-Idp-Roles")),
        credential_class=_credential_class(_header(request, "X-Idp-Credential-Class")),
        audience=_audience_for(request.url.path),
        client_surface=_header(request, "X-Idp-Client-Surface"),
    )


PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_principal)]


async def get_tenant(container: ContainerDep, principal: PrincipalDep) -> TenantContext:
    """Admit the caller's organisation: trusted identity **plus** registry state.

    Both halves are required. The validated ``tid`` says which organisation a person belongs to;
    the registry says whether that organisation may currently be served. Neither alone is
    admission.

    The result is constructed by
    :meth:`~ragcore.domain.tenancy.TenantContext.from_admitted_identity`, whose name records the
    provenance. There is no constructor that takes a tenant from a request.

    Raises:
        HTTPException: 403 for an unknown or non-admitted organisation. **Fails closed**: an
            organisation the registry does not know is not admitted, and an unavailable registry
            raises rather than defaulting to admitted.
    """
    if container.tenant_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The tenant registry is not available.",
        )

    tenant = await container.tenant_registry.admit_end_user(principal.identity.tenant_id)
    if tenant is None or not tenant.is_admitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This organisation is not currently admitted.",
        )

    # Tag this task's telemetry with the organisation, from the one place admission actually
    # happens. Traces, metrics and logs are each tagged from trusted context and never from a
    # supplied header or from message content (spec FR-OPS-002) — binding it here rather than in
    # middleware is what makes that true, because middleware runs before the registry has been
    # consulted and would be tagging with an unadmitted claim.
    bind_tenant(tenant)

    return tenant


TenantDep = Annotated[TenantContext, Depends(get_tenant)]


def _roles(raw: str) -> RoleSet:
    """Parse the role header.

    An unrecognised role name is **dropped**, not an error. Roles are additive capabilities and
    the platform's set is closed: a role it does not know confers nothing, so a directory that
    grows a group this release has never heard of does not break every request from that tenant.
    """
    parsed = [StaffRole.parse(name.strip()) for name in raw.split(",") if name.strip()]
    return RoleSet.of(*[role for role in parsed if role is not None])


def _credential_class(raw: str) -> CredentialClass:
    """Parse the credential class, defaulting to delegated.

    Delegated is the safe default: it is the *narrower* of the two. Defaulting to ``APP`` would
    mean a missing header produced a workload principal, and the Workload is the principal that
    executes.
    """
    return CredentialClass.APP if raw.lower() == "app" else CredentialClass.DELEGATED


__all__ = [
    "IDENTITY_HEADERS",
    "ContainerDep",
    "CorrelationDep",
    "PrincipalDep",
    "TenantDep",
    "get_container",
    "get_correlation_id",
    "get_principal",
    "get_tenant",
]
