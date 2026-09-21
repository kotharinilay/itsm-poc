"""The authenticated principal, and the closed Gateway-derived header contract.

Identity is derived exactly once, at the Gateway. Services MUST NOT parse an access token and
consume only this contract (A1 §4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from ragcore.domain.identifiers import EntraTenantId, PrincipalId
from ragcore.domain.roles import RoleSet, StaffRole


class CredentialClass(Enum):
    """Whether a request arrived on a delegated (human) or app-only (workload) credential."""

    DELEGATED = "delegated"
    APP = "app"


class Audience(Enum):
    """The resource audience a request was addressed to.

    **The surface decides which authorization model applies**, and a person cannot promote
    themselves by anything they supply (spec FR-SURF-005). This comes from the route the
    Gateway matched, never from a request field.
    """

    CUSTOMER = "customer"
    STAFF = "staff"
    WORKLOAD = "workload"


IDENTITY_HEADERS: Final[tuple[str, ...]] = (
    "X-Idp-Tenant-Id",
    "X-Idp-Principal-Id",
    "X-Idp-Roles",
    "X-Idp-Credential-Class",
    "X-Idp-Client-Surface",
)
"""The closed header contract (specification 11.5). Services do not invent alternatives."""


@dataclass(frozen=True, slots=True)
class HumanIdentity:
    """Human identity: ``(tid, oid)``, and nothing else is an identity key."""

    tenant_id: EntraTenantId
    principal_id: PrincipalId


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """The principal for one request, as derived at the Gateway."""

    identity: HumanIdentity
    roles: RoleSet
    credential_class: CredentialClass
    audience: Audience
    client_surface: str

    @property
    def authorizable_roles(self) -> RoleSet:
        """The roles that may be consulted for a decision on this request.

        **This is where the surface rule becomes structural rather than remembered.** Any
        person acting on a customer surface is an end user — including staff — and their staff
        roles MUST NOT be consulted there (A1 §6). Rather than trusting
        every call site to remember that, the customer audience returns a set that simply does
        not contain them.
        """
        if self.audience is Audience.CUSTOMER:
            return RoleSet.of(StaffRole.END_USER)
        return self.roles
