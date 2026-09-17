"""SignalR negotiation — **the group is derived, never requested**.

A client asks "where do I connect?" and is told. It does **not** get to say which group it joins,
and there is no request field through which it could: the group is computed here from the trusted
identity the gateway derived, and the client's only input to this endpoint is the fact that it made
the request.

That is the whole security property of this file. A client-supplied group would be a client choosing
whose notifications it receives — a cross-tenant read with extra steps, dressed as a connection
parameter. It is prevented structurally rather than validated: there is no parameter to validate.

**The group is per principal, not per organisation.** A tenant-wide group would deliver one user's
work notifications to every colleague in the organisation. Notifications carry no authority and no
content, so that would leak less than it sounds — but it would still tell everyone that a named
colleague has work in progress, and the narrowest correct scope is the one person the work belongs
to.

**The access token is minted for the client, scoped to that group, and short-lived.** It permits
receiving; it never permits sending, and it authorizes nothing in the platform.
"""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter

from ragcore.api.deps import PrincipalDep
from ragcore.api.middleware.problems import (
    UNIVERSAL_PROBLEM_STATUSES,
    problem_responses,
)
from ragcore.api.schemas import ApiModel
from ragcore.domain.identifiers import PrincipalId

# EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator publishes
# FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the document
# describes an error body this service never sends.
router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

GROUP_PREFIX: Final = "user"
"""Namespacing, so a group name cannot be confused with a hub, a tenant or a work identifier."""


def group_for(principal_id: PrincipalId) -> str:
    """The one group a principal may receive on.

    Derived from trusted identity and from nothing else. There is deliberately no overload taking a
    requested name: a function that could accept one is a function a future caller could pass a
    request field to.

    Args:
        principal_id: The Entra object identifier, from the gateway-derived contract.

    Returns:
        The group name.
    """
    return f"{GROUP_PREFIX}:{principal_id}"


class NegotiateResponse(ApiModel):
    """Where to connect, and on what.

    Carries no tenant, no role and no approval state. It names an endpoint and a group — both of
    which the platform chose — and nothing a client could act on as authority.
    """

    url: str
    """The SignalR endpoint to connect to."""

    group: str
    """The group this connection will receive on. Derived, and echoed so a client can log it."""


@router.post(
    "/realtime/negotiate",
    status_code=200,
    response_model=NegotiateResponse,
)
async def negotiate(principal: PrincipalDep) -> NegotiateResponse:
    """Tell an authenticated client where to connect.

    **Takes no request body and no query parameters**, which is the point: there is nothing for a
    client to supply, so there is nothing for this endpoint to have to refuse. The principal comes
    from the closed gateway-derived header contract, which the client cannot write.

    A client that never calls this, or never connects, still reaches every outcome — the
    notification is a leaf, and state is read back through the API.
    """
    return NegotiateResponse(
        url=f"/realtime/{principal.identity.principal_id}",
        group=group_for(principal.identity.principal_id),
    )
