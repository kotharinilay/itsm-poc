"""Domain types for the catalogue, the registry and the access decision.

Pure model: no I/O, no framework, no provider type. `tests/architecture/test_layering.py` asserts
that.

**The type split here is the control, not a modelling preference.** Three separate types exist where
one dictionary would have done, and each separation prevents a specific mistake:

* :class:`CapabilityIdentity` — a catalogue id **and** its version, always together. A capability
  referenced without its version is a capability whose approval could have been granted against
  different behaviour.
* :class:`Capability` — what a caller may *see*. It carries **no treatment, no accepted roles and no
  endpoint**, so there is no field a caller could read to decide whether to proceed.
* :class:`ConnectorBinding` — what the service *executes with*. It carries the endpoint. It is never
  returned from an API.

The gap between :class:`Capability` and :class:`ConnectorBinding` is the same gap the MCP client
enforces between an advertised tool and an invocable one: going from one to the other means going
through the registry, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "AccessDecision",
    "AccessRefusal",
    "Capability",
    "CapabilityIdentity",
    "ConnectorBinding",
    "ConnectorKind",
    "IdempotencyPolicy",
]


class ConnectorKind(Enum):
    """How a connector is reached."""

    NATIVE = "native"
    MCP = "mcp"


class IdempotencyPolicy(Enum):
    """Whether an invocation carries a derived idempotency key.

    `NONE` exists for genuinely read-only capabilities. It is **not** an opt-out for a
    side-effecting one: a write without a key is a write that a redelivered command performs twice,
    and the execution path refuses that combination rather than trusting the row.
    """

    DERIVED_KEY = "derived_key"
    NONE = "none"


class AccessRefusal(Enum):
    """Why a capability may not be used. **Each value needs a different operator action.**

    Kept distinct rather than collapsed into one "denied", because `FR-EXT-022` requires *entitled
    but unreachable* to be reported differently from *not entitled* — and because an operator
    reading "denied" learns nothing about whether to entitle an organisation, register a capability,
    or fix a system.
    """

    NOT_ENTITLED = "not_entitled"
    """The organisation has no enabled entitlement. Operator action: entitle it."""

    NOT_REGISTERED = "not_registered"
    """No catalogue entry. Discovery never confers entitlement, so an advertised tool lands here."""

    VERSION_MISMATCH = "version_mismatch"
    """Registered, but not at the version that was authorized. The approval bound a version."""

    NO_BINDING = "no_binding"
    """Registered and entitled, but nothing says how to run it. A config gap, not a denial."""


@dataclass(frozen=True, slots=True)
class CapabilityIdentity:
    """A catalogue entry at a specific version.

    Attributes:
        catalogue_id: The capability's platform identifier.
        version: The catalogue version in force. **Never defaulted** — a default would let a caller
            omit it and be silently served whatever is current, which is how an approval granted
            against version 2 comes to execute version 3.
    """

    catalogue_id: str
    version: int

    def __post_init__(self) -> None:
        """Reject a malformed identity at construction.

        Raises:
            ValueError: When the identifier is blank or the version is below one. Catalogue versions
                start at one in `platform.governance_record`, so zero is not "unset" — it is a value
                that joins to nothing and would be discovered only at execution.
        """
        if not self.catalogue_id.strip():
            raise ValueError("a catalogue identifier is required")
        if self.version < 1:
            raise ValueError(
                f"catalogue version must be >= 1, got {self.version}. Versions start at one; zero "
                "is not an unset marker and would join to no catalogue entry."
            )


@dataclass(frozen=True, slots=True)
class Capability:
    """One capability as a caller may see it.

    **Deliberately without treatment, accepted roles, risk tier or endpoint.** Treatment is
    deterministic governance's decision in RagCore (`FR-INTEG-008`); returning it here would invite
    a caller to read it and decide. The endpoint is execution detail and would be an egress hint.

    Attributes:
        identity: What it is, and at which version.
        kind: `read` or `action`, from the governance record. Carried because a caller legitimately
            distinguishes a capability that observes from one that changes something — but an
            `action` is still never callable from the agent loop.
        entitled: Whether this organisation may use it.
        available: Whether its system is reachable. **Separate from `entitled` on purpose**
            (`FR-EXT-022`): *entitled but unreachable* and *not entitled* need different operator
            actions, and neither may be presented to a user as a failure of their request.
        is_reference_fixture: True for the inert scaffold fixtures, so a fixture is **visibly**
            labelled wherever it appears and can never read as product capability.
    """

    identity: CapabilityIdentity
    kind: str
    entitled: bool
    available: bool
    is_reference_fixture: bool


@dataclass(frozen=True, slots=True)
class ConnectorBinding:
    """How one capability actually executes. **Never returned from an API.**

    Attributes:
        identity: The capability this binds, at its version.
        connector_id: The owning connector.
        base_endpoint: The connector's absolute base URL, from the registry.
        operation_path: The path appended to it.
        signing_profile: A Key Vault secret **name**, or ``None``. Never a value.
        idempotency_policy: Whether a derived key is carried.
        is_reference_fixture: True when this binds an inert fixture.
    """

    identity: CapabilityIdentity
    connector_id: str
    base_endpoint: str
    operation_path: str
    signing_profile: str | None
    idempotency_policy: IdempotencyPolicy
    is_reference_fixture: bool

    @property
    def destination(self) -> str:
        """The absolute URL this capability invokes.

        **The only place a destination is assembled, and both halves come from the registry**
        (spec `FR-EXT-018`). Nothing here reads a parameter, a model output or retrieved content —
        a destination derived from any of those is the egress hole the governance model exists to
        close, and the way that hole usually opens is a helper that accepts an override.

        Returns:
            The URL.
        """
        return f"{self.base_endpoint.rstrip('/')}/{self.operation_path.lstrip('/')}"


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """The outcome of the execution-time access and policy re-check.

    **A refusal is a value, not an exception.** These are expected outcomes — an organisation that
    is not entitled is ordinary, not exceptional — and modelling them as returns forces the caller
    to handle them. An exception here would be caught somewhere generic and logged as a failure,
    which is how "not entitled" comes to look like "the system is broken".

    Attributes:
        binding: The binding to execute with, present **only** when permitted. Absent on refusal,
            so there is no way to hold a refusal and still reach an endpoint.
        refusal: Why not, when not.
    """

    binding: ConnectorBinding | None
    refusal: AccessRefusal | None

    @property
    def permitted(self) -> bool:
        """Whether execution may proceed."""
        return self.binding is not None and self.refusal is None

    @classmethod
    def allow(cls, binding: ConnectorBinding) -> AccessDecision:
        """Permit execution with this binding."""
        return cls(binding=binding, refusal=None)

    @classmethod
    def refuse(cls, refusal: AccessRefusal) -> AccessDecision:
        """Refuse, with a reason an operator can act on."""
        return cls(binding=None, refusal=refusal)
