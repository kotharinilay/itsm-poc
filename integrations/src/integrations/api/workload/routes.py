"""The workload API. **The organisation is never a parameter.**

Two synchronous operations (`contracts/integrations-api.md`):

* `GET  /api/workload/v1/integrations/catalogue` — the tenant-resolved capability set.
* `POST /api/workload/v1/integrations/case-operations` — an inert case-like system-of-record
  operation.

**There is deliberately no execution endpoint.** Normal tool execution is a Service Bus command
(`FR-INTEG-013`); a synchronous execution route would be a second, ungoverned path to the same
effect.

**Every request carries an opaque identifier and none carries an organisation.** A workload token's
`tid` is the *Operator* tenant, never a customer's, so the organisation is recovered from the
durable object the identifier names (`FR-INTEG-018`). That is why these routes take `sessionId` or
`workItemId` and why there is no `tenantId` parameter anywhere — one would be a caller asserting
authority the platform derives, which `contracts/README.md` rule 1 forbids outright.

**A missing or foreign object is 404, not 403.** Existence is itself organisation-scoped
information: answering 403 for "exists but not yours" and 404 for "does not exist" lets a caller map
another organisation's identifiers by the difference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from integrations.api.middleware.correlation import current_correlation_id
from integrations.api.middleware.problems import (
    UNIVERSAL_PROBLEM_STATUSES,
    ProblemJSONResponse,
    problem,
    problem_responses,
)
from integrations.credentials.resolver import CredentialNotEntitledError
from integrations.domain.catalogue import AccessRefusal, CapabilityIdentity
from integrations.egress.http import EgressError
from integrations.execution.normalization import BoundaryValidationError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.config.composition import Container

__all__ = ["build_workload_router"]


def _camel(field: str) -> str:
    """Convert a snake_case field name to the camelCase the wire contract uses.

    Args:
        field: The Python field name.

    Returns:
        The wire name.
    """
    head, *rest = field.split("_")
    return head + "".join(part.capitalize() for part in rest)


class _ApiModel(BaseModel):
    """camelCase both directions, and no field the contract does not name."""

    # `extra="forbid"` is the control, not a style choice: an organisation supplied as `tenantId` is
    # REFUSED rather than ignored. Ignoring it would let a caller believe it had been honoured.
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


class CapabilityModel(_ApiModel):
    """One capability as a caller may see it.

    **No treatment, no accepted roles, no risk tier, no endpoint.** Treatment is deterministic
    governance's decision in RagCore; returning it would invite a caller to read it and decide. The
    endpoint is execution detail and would be an egress hint.
    """

    catalogue_id: str
    catalogue_version: int
    kind: str
    entitled: bool = Field(
        description="Whether this organisation may use the capability.",
    )
    available: bool = Field(
        description=(
            "Whether its system is reachable. Separate from `entitled` on purpose: entitled but "
            "unreachable and not entitled need different operator actions, and neither may be "
            "presented to a user as a failure of their request."
        ),
    )
    is_reference_fixture: bool = Field(
        description="True for an inert scaffold fixture. Never product capability.",
    )


class CatalogueResponse(_ApiModel):
    """The capability set for one organisation."""

    items: list[CapabilityModel]
    next_cursor: str | None = None


class CaseOperationRequest(_ApiModel):
    """A synchronous system-of-record operation.

    **No `tenantId`.** The organisation is recovered from the durable object `sessionId` names.
    """

    session_id: UUID
    catalogue_id: str
    catalogue_version: int
    idempotency_key: str = Field(
        min_length=8,
        description=(
            "The DERIVED key, supplied by the caller that owns the authority record. Derived, "
            "never random, so a repeat of the same logical action is recognised as a repeat."
        ),
    )
    parameters: dict[str, object] = Field(default_factory=dict)


class CaseOperationResponse(_ApiModel):
    """What the system of record returned, normalized."""

    succeeded: bool
    external_reference: str | None
    payload: dict[str, object]


_REFUSAL_DETAIL = {
    AccessRefusal.NOT_ENTITLED: "This organisation is not entitled to the capability.",
    AccessRefusal.NOT_REGISTERED: "The capability is not registered in the catalogue.",
    AccessRefusal.VERSION_MISMATCH: "The capability version does not match the registered one.",
    AccessRefusal.NO_BINDING: "The capability has no connector binding configured.",
}


def build_workload_router(container: Container) -> APIRouter:
    """Build the workload router.

    Args:
        container: The composed dependencies.

    Returns:
        The router.
    """
    # EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator
    # publishes FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the
    # document describes an error body this service never sends — and a client written against it
    # parses the wrong shape on the one path it cannot test against a happy case.
    #
    # 502 and 503 are declared HERE and on no other audience in the platform: this is the only
    # service that calls an external system, so it is the only one that can report a capability as
    # temporarily unavailable rather than failed.
    router = APIRouter(
        prefix="/api/workload/v1/integrations",
        tags=["workload"],
        responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES, 400, 502, 503),
    )

    @router.get("/catalogue", response_model=CatalogueResponse)
    async def read_catalogue(
        request: Request,
        session_id: Annotated[UUID | None, Query(alias="sessionId")] = None,
        work_item_id: Annotated[UUID | None, Query(alias="workItemId")] = None,
    ) -> CatalogueResponse | ProblemJSONResponse:
        """The capability set entitled to the organisation the identifier names.

        Exactly one of `sessionId` or `workItemId` is required. Both or neither is a 400 rather than
        a precedence rule: a caller supplying both has two different ideas about which organisation
        this is, and silently preferring one would resolve that disagreement invisibly.
        """
        if (session_id is None) == (work_item_id is None):
            return problem(
                status=400,
                title="Bad Request",
                detail="Supply exactly one of sessionId or workItemId.",
                kind="invalid-request",
                instance=request.url.path,
            )

        tenant_id = (
            await container.tenants.tenant_for_session(session_id)
            if session_id is not None
            else await container.tenants.tenant_for_work_item(work_item_id)  # type: ignore[arg-type]
        )
        if tenant_id is None:
            return problem(
                status=404,
                title="Not Found",
                detail="No such object.",
                kind="not-found",
                instance=request.url.path,
            )

        capabilities = await container.catalogue.capabilities_for(tenant_id)
        return CatalogueResponse(
            items=[
                CapabilityModel(
                    catalogue_id=c.identity.catalogue_id,
                    catalogue_version=c.identity.version,
                    kind=c.kind,
                    entitled=c.entitled,
                    available=c.available,
                    is_reference_fixture=c.is_reference_fixture,
                )
                for c in capabilities
            ],
            next_cursor=None,
        )

    @router.post("/case-operations", response_model=CaseOperationResponse)
    async def create_case(
        request: Request, body: CaseOperationRequest
    ) -> CaseOperationResponse | ProblemJSONResponse:
        """Perform a synchronous system-of-record operation.

        The **full execution-time re-check runs here** even though the caller has already gated the
        operation (`FR-INTEG-019`). Prior retrieval is not standing permission, and an entitlement
        revoked between proposal and execution is ordinary rather than exceptional.
        """
        tenant_id = await container.tenants.tenant_for_session(body.session_id)
        if tenant_id is None:
            return problem(
                status=404,
                title="Not Found",
                detail="No such session.",
                kind="not-found",
                instance=request.url.path,
            )

        identity = CapabilityIdentity(
            catalogue_id=body.catalogue_id, version=body.catalogue_version
        )
        decision = await container.access_policy.evaluate(tenant_id, identity)
        if not decision.permitted:
            refusal = decision.refusal
            return problem(
                status=403,
                title="Forbidden",
                detail=_REFUSAL_DETAIL[refusal] if refusal else "Refused.",
                kind=refusal.value.replace("_", "-") if refusal else "forbidden",
                instance=request.url.path,
            )

        if container.servicenow is None:
            # Honest rather than a stubbed success (constitution Principle IX). A service deployed
            # without the connector bound reports that it cannot act; it does not pretend to.
            return problem(
                status=503,
                title="Service Unavailable",
                detail="The system-of-record connector is not available.",
                kind="capability-unavailable",
                instance=request.url.path,
            )

        try:
            result = await container.servicenow.create_case(
                binding=decision.binding,  # type: ignore[arg-type]
                tenant_id=tenant_id,
                parameters=body.parameters,
                idempotency_key=body.idempotency_key,
                correlation_id=current_correlation_id(),
            )
        except CredentialNotEntitledError:
            return problem(
                status=403,
                title="Forbidden",
                detail="This organisation holds no credential for the capability.",
                kind="not-entitled",
                instance=request.url.path,
            )
        except (EgressError, BoundaryValidationError):
            # ENTITLED BUT UNREACHABLE, reported distinctly from not entitled (spec FR-EXT-022) and
            # never as a failure of the user's request. 502 rather than 500: the failure is the far
            # side's, and conflating the two sends an operator to the wrong system.
            return problem(
                status=502,
                title="Bad Gateway",
                detail="The system of record is temporarily unavailable.",
                kind="capability-unavailable",
                instance=request.url.path,
            )

        return CaseOperationResponse(
            succeeded=result.succeeded,
            external_reference=result.external_reference,
            payload=dict(result.payload),
        )

    return router
