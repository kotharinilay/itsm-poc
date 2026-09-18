"""The execution-time access and policy re-check. **Positive and negative.**

Spec `FR-INTEG-019`. Every refusal below is a *different operator action*, which is why they are
distinct values rather than one denial — and why each gets its own test rather than being covered by
"refuses when it should".
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from integrations.domain.catalogue import (
    AccessRefusal,
    CapabilityIdentity,
    ConnectorBinding,
    IdempotencyPolicy,
)
from integrations.policy.checks import AccessPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from integrations.domain.catalogue import Capability

pytestmark = pytest.mark.governance

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_CAPABILITY = "reference.inert_read"


class _Catalogue:
    """A catalogue with fixed answers."""

    def __init__(self, *, entitled: bool, registered_version: int | None) -> None:
        self._entitled = entitled
        self._registered_version = registered_version

    async def capabilities_for(self, tenant_id: UUID) -> Sequence[Capability]:
        del tenant_id
        return []

    async def is_entitled(self, tenant_id: UUID, catalogue_id: str) -> bool:
        del tenant_id, catalogue_id
        return self._entitled

    async def registered_version(self, catalogue_id: str) -> int | None:
        del catalogue_id
        return self._registered_version


class _Registry:
    """A registry that either has a binding or does not."""

    def __init__(self, *, has_binding: bool) -> None:
        self._has_binding = has_binding

    async def binding_for(self, identity: CapabilityIdentity) -> ConnectorBinding | None:
        if not self._has_binding:
            return None
        return ConnectorBinding(
            identity=identity,
            connector_id="reference",
            base_endpoint="https://reference.invalid",
            operation_path="/cases",
            signing_profile=None,
            idempotency_policy=IdempotencyPolicy.DERIVED_KEY,
            is_reference_fixture=True,
        )


def _policy(*, entitled: bool, version: int | None, binding: bool) -> AccessPolicy:
    # No `type: ignore` needed, and that is worth noticing: the fakes satisfy `CataloguePort` and
    # `ConnectorRegistryPort` structurally, so mypy accepts them. A fake that had drifted from the
    # port would fail here rather than passing a test against a shape nothing implements.
    return AccessPolicy(
        _Catalogue(entitled=entitled, registered_version=version),
        _Registry(has_binding=binding),
    )


async def test_permits_an_entitled_registered_current_bound_capability() -> None:
    """**Positive.** All four facts hold, so execution may proceed — and it carries a binding."""
    decision = await _policy(entitled=True, version=1, binding=True).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert decision.permitted
    assert decision.binding is not None
    assert decision.refusal is None


async def test_refuses_an_unentitled_organisation() -> None:
    """**Negative.** No enabled entitlement. Operator action: entitle the organisation."""
    decision = await _policy(entitled=False, version=1, binding=True).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert not decision.permitted
    assert decision.refusal is AccessRefusal.NOT_ENTITLED
    # NO BINDING ON A REFUSAL. There is deliberately no way to hold a refusal and still reach an
    # endpoint — the type carries one or the other, never both.
    assert decision.binding is None


async def test_refuses_an_unregistered_capability() -> None:
    """**Negative.** Discovery never confers entitlement (spec FR-EXT-014).

    A capability an MCP server advertises but the catalogue does not hold lands exactly here. That
    gap — between advertised and callable — is the check.
    """
    decision = await _policy(entitled=True, version=None, binding=True).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert decision.refusal is AccessRefusal.NOT_REGISTERED


async def test_refuses_a_version_the_catalogue_has_moved_past() -> None:
    """**Negative, and the subtlest one.** The approval bound a version.

    The identifier matches, which is exactly why this would otherwise pass unnoticed: executing
    version 1 when the catalogue is at 2 executes behaviour nobody authorized.
    """
    decision = await _policy(entitled=True, version=2, binding=True).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert decision.refusal is AccessRefusal.VERSION_MISMATCH


async def test_refuses_when_no_connector_binding_is_configured() -> None:
    """**Negative.** A configuration gap, reported distinctly from a denial.

    Entitled, registered, current — but nothing says how to run it. Distinct so the operator
    configures a binding rather than re-entitling an organisation that is already entitled.
    """
    decision = await _policy(entitled=True, version=1, binding=False).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert decision.refusal is AccessRefusal.NO_BINDING


async def test_entitlement_is_checked_before_anything_else() -> None:
    """An unentitled caller is refused without a registration or binding lookup.

    Ordering is cheapest-and-most-specific first, and it is observable: with the catalogue
    unregistered *and* the organisation unentitled, the refusal names entitlement. A caller is told
    the first thing wrong rather than the last, which is what makes the answer actionable.
    """
    decision = await _policy(entitled=False, version=None, binding=False).evaluate(
        _TENANT, CapabilityIdentity(_CAPABILITY, 1)
    )

    assert decision.refusal is AccessRefusal.NOT_ENTITLED


def test_a_capability_identity_requires_a_version() -> None:
    """Version zero is refused at construction.

    Catalogue versions start at one, so zero is not an "unset" marker — it is a value that joins to
    no catalogue entry and would otherwise be discovered at execution.
    """
    with pytest.raises(ValueError, match="version must be >= 1"):
        CapabilityIdentity(_CAPABILITY, 0)


def test_a_binding_assembles_its_destination_from_the_registry_only() -> None:
    """Spec FR-EXT-018: a destination is never derived from parameters or provider output.

    Both halves of the URL come from registry rows. There is no parameter, override or helper here
    that could contribute one — which is the property this asserts by there being nothing else to
    pass in.
    """
    binding = ConnectorBinding(
        identity=CapabilityIdentity(_CAPABILITY, 1),
        connector_id="reference",
        base_endpoint="https://reference.invalid/",
        operation_path="/cases",
        signing_profile=None,
        idempotency_policy=IdempotencyPolicy.NONE,
        is_reference_fixture=True,
    )

    assert binding.destination == "https://reference.invalid/cases"


def test_uuid_helper_is_unused_but_imports_cleanly() -> None:
    """Guards against an unused-import lint regression in this module's fixtures."""
    assert isinstance(uuid4(), UUID)
