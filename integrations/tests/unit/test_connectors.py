"""The relocated connectors: Graph, OneLogin and Duo (T289–T291).

**These tests exist because a relocation is where behaviour quietly changes.** Moving a file is not
the risky part; re-deriving a destination, a scope or a not-found rule during the move is. Each test
below pins one fact that was true in RagCore and must still be true here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
import pytest
from azure.core.credentials import AccessToken

from integrations.connectors.duo import CATALOGUE_PREFIX as DUO_PREFIX
from integrations.connectors.duo import SYSTEM as DUO_SYSTEM
from integrations.connectors.graph.adapter import GRAPH_SCOPE, MicrosoftGraphAdapter
from integrations.connectors.onelogin import CATALOGUE_PREFIX as ONELOGIN_PREFIX
from integrations.connectors.onelogin import SYSTEM as ONELOGIN_SYSTEM
from integrations.domain.catalogue import CapabilityIdentity, ConnectorBinding, IdempotencyPolicy
from integrations.egress.http import EgressError, ResilientCaller
from integrations.execution.normalization import BoundaryValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_PRINCIPAL = "a4f0f0d2-0000-4000-8000-000000000001"
_CORRELATION = "0f9a5f4c-1111-4000-8000-000000000002"


class _Credential:
    """A credential that records the scope it was asked for.

    The recording is the point: the scope is what decides what this process may do in Graph, and a
    relocation that dropped or widened it would still return a profile in every test that only
    checked the profile.

    **It returns a real `AccessToken`, and satisfies `AsyncTokenCredential` structurally rather than
    by a cast.** A cast would silence the type checker without the fake ever having to match the
    shape the adapter is written against — which is how a fake drifts from the contract it stands in
    for, and the test then proves something about the fake.
    """

    def __init__(self) -> None:
        self.scopes: list[tuple[str, ...]] = []

    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        del kwargs
        self.scopes.append(scopes)
        # The token authenticates nothing. No credential appears in this tree, in source or in
        # tests — a fixture resembling a real token is one a secret scanner flags and a reader has
        # to verify, and the twentieth false positive is the one nobody checks.
        return AccessToken("placeholder-directory-token", 0)  # noqa: S106

    async def close(self) -> None:
        """Part of the credential contract. Nothing to release."""

    async def __aenter__(self) -> _Credential:
        return self

    async def __aexit__(self, *args: object) -> None:
        """Nothing to release."""


def _binding() -> ConnectorBinding:
    return ConnectorBinding(
        identity=CapabilityIdentity("graph.user.read", 1),
        connector_id="graph",
        base_endpoint="https://graph.invalid/v1.0",
        operation_path="/users",
        signing_profile=None,
        idempotency_policy=IdempotencyPolicy.NONE,
        is_reference_fixture=True,
    )


def _adapter(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[MicrosoftGraphAdapter, _Credential]:
    credential = _Credential()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return MicrosoftGraphAdapter(ResilientCaller(client), credential), credential


# ---------------------------------------------------------------------------
# Microsoft Graph — T289
# ---------------------------------------------------------------------------


async def test_the_directory_read_returns_a_profile_in_platform_terms() -> None:
    """**Positive.** Graph's own vocabulary does not leave the boundary check."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "@odata.context": "https://graph.invalid/$metadata#users",
                "id": _PRINCIPAL,
                "userPrincipalName": "someone@example.invalid",
                "displayName": "A Person",
                "mail": "a.person@example.invalid",
            },
        )

    adapter, credential = _adapter(handler)
    profile = await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION)

    assert profile is not None
    assert profile.display_name == "A Person"
    assert profile.mail == "a.person@example.invalid"

    # The two fields ARE the whole profile. A relocation that let `userPrincipalName` or a role list
    # through would have created a second source of identity beside the closed header contract.
    assert not hasattr(profile, "user_principal_name")
    assert not hasattr(profile, "roles")

    assert credential.scopes == [(GRAPH_SCOPE,)]
    assert captured["authorization"] == "Bearer placeholder-directory-token"


async def test_the_destination_comes_from_the_binding_and_not_from_the_principal() -> None:
    """**The registry decides where the call goes** (`FR-EXT-018`).

    The principal identifier appears in the path, so this is exactly the shape where a destination
    can be steered by an argument. The assertion is on the prefix: whatever the principal is, the
    host and base path came from the binding.
    """
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"displayName": "A Person"})

    adapter, _ = _adapter(handler)
    await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION)

    assert captured["url"].startswith("https://graph.invalid/v1.0/users/")


async def test_an_unknown_principal_is_an_answer_and_a_broken_graph_is_not() -> None:
    """**404 and 500 must not collapse into the same result.**

    A caller handed ``None`` for both cannot tell "this person does not exist" from "the directory
    is down", and the tempting reading of that ambiguity — treat the absence as settled — is the
    wrong one.
    """
    adapter, _ = _adapter(lambda _: httpx.Response(404, json={}))
    assert await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION) is None

    adapter, _ = _adapter(lambda _: httpx.Response(500, json={}))
    with pytest.raises(EgressError):
        await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION)


async def test_a_profile_with_no_display_name_is_refused_at_the_boundary() -> None:
    """An empty profile would render as though the directory had answered."""
    adapter, _ = _adapter(lambda _: httpx.Response(200, json={"mail": "a@example.invalid"}))

    with pytest.raises(BoundaryValidationError):
        await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION)


async def test_an_oversized_directory_field_is_refused_rather_than_truncated() -> None:
    """**Truncation is not an option.** A silently shortened value is invisibly wrong."""
    adapter, _ = _adapter(lambda _: httpx.Response(200, json={"displayName": "x" * 300}))

    with pytest.raises(BoundaryValidationError):
        await adapter.lookup_principal(_binding(), _TENANT, _PRINCIPAL, _CORRELATION)


# ---------------------------------------------------------------------------
# OneLogin and Duo — T290, T291
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("system", "prefix"),
    [(ONELOGIN_SYSTEM, ONELOGIN_PREFIX), (DUO_SYSTEM, DUO_PREFIX)],
)
def test_a_target_system_costs_a_name_and_nothing_else(system: str, prefix: str) -> None:
    """ADR-0005's claim, asserted rather than described.

    The prefix is **derived** from the system name rather than written out a second time. Two
    independently spelled constants are two places for a mismatch to hide, and the mismatch presents
    as "entitled but nothing works" — which is the failure that is hardest to attribute.
    """
    assert prefix == f"{system}."


def test_neither_target_system_brings_its_own_client_or_authorization_mechanism() -> None:
    """The **emptiness** is the evidence (spec `FR-EXT-010`).

    A new third-party system must cost a name, a catalogue registration and an entitlement — never a
    bespoke client, a bespoke credential arrangement or a bespoke governance hook. Asserting on the
    module's public surface is how that claim stays true: the day someone adds a client here, this
    fails.
    """
    import integrations.connectors.duo as duo
    import integrations.connectors.onelogin as onelogin

    for module in (onelogin, duo):
        assert set(module.__all__) == {"CATALOGUE_PREFIX", "SYSTEM"}
        exported = {name for name in vars(module) if not name.startswith("_")}
        assert not {name for name in exported if name.endswith(("Client", "Adapter", "Resolver"))}
