"""The edge path is defined once and enforced on both stacks.

**The rule is cross-platform and the registry is shared.** ``build/policy/edge-trust.json`` defines
the only path by which an application API request may reach a backend — Front Door + WAF, then APIM,
then the backend — and the controls that make that path provable rather than merely intended. The
.NET side enforces the same file from
``dotnet/tests/Synthia.ArchitectureTests/EdgeTrustPolicyTests.cs``, and
:class:`TestBothPlatformsEnforceTheSamePolicy` asserts the two agree — because two hand-maintained
lists drift, and the drift is invisible until the day the weaker of the two is the one that
mattered.

**Structural, not runtime.** These read source and committed configuration rather than deploying
anything, so the rules hold in CI without an Azure subscription and a failure names the file and the
construct rather than surfacing as a 403 in an environment somebody has to reproduce.

**There is no behavioural half any more.** It lived in ``test_gateway_provenance.py`` and asserted
that a forged identity contract sent from inside the network was refused on gateway provenance.
That mechanism is deferred — see
``docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md`` — and nothing replaced
it, so the assertion stopped being true and the file was removed rather than
softened into one that passes. What this module now guards instead is that the deferral stays
*recorded* and stays *unreplaced* — see
:meth:`TestEveryHopDeclaresItsControls.test_a_hop_without_an_application_control_says_so_explicitly`.

**Why the infrastructure is asserted at all.** Half of this boundary lives outside the application —
in an APIM policy, a Front Door definition, an ingress manifest — where no compiler and no unit test
would otherwise look. Those are also the files where a one-line change (``external: true``, a
deleted ``set-header``) reviews well and deploys quietly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from ragcore.domain.principal import IDENTITY_HEADERS

ROOT: Final = Path(__file__).resolve().parents[3]
"""The repository root — ``ragcore/tests/security`` is three levels down."""

POLICY_PATH: Final = ROOT / "build" / "policy" / "edge-trust.json"
APIM: Final = ROOT / "build" / "infra" / "apim"
DOTNET_ENFORCER: Final = (
    ROOT / "dotnet" / "tests" / "Synthia.ArchitectureTests" / "EdgeTrustPolicyTests.cs"
)


@pytest.fixture(name="policy", scope="module")
def policy_fixture() -> dict[str, Any]:
    """The shared registry both stacks read."""
    assert POLICY_PATH.is_file(), (
        f"the shared edge trust policy is missing: {POLICY_PATH}. Both deployables read this one "
        "file; without it neither rule enforces anything."
    )
    # Bound to an annotated local rather than returned straight from `json.loads`, which is typed
    # `Any`. The same pattern as `test_azure_identity.py`: returning `Any` from a function declared
    # to return a mapping silently disables type checking on every use of this fixture.
    loaded: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return loaded


def _production_sources() -> list[Path]:
    """Every production Python file, excluding tests and the virtual environment."""
    return [
        path for path in (ROOT / "ragcore" / "src").rglob("*.py") if "__pycache__" not in path.parts
    ]


# ---------------------------------------------------------------------------
# The chain the policy defines
# ---------------------------------------------------------------------------


class TestEveryHopDeclaresItsControls:
    """ "Neither control is sufficient alone" (spec 10.3) is a claim about *pairs*.

    One hop no longer has a pair. That is recorded rather than asserted away: see
    :meth:`test_a_hop_without_an_application_control_says_so_explicitly`.
    """

    def test_the_chain_is_client_to_front_door_to_apim_to_backend(
        self, policy: dict[str, Any]
    ) -> None:
        """The three hops, in order, with nothing between them."""
        assert [hop["id"] for hop in policy["chain"]["hops"]] == [
            "client-to-frontdoor",
            "frontdoor-to-apim",
            "apim-to-backend",
        ]

    def test_every_hop_names_a_network_control(self, policy: dict[str, Any]) -> None:
        """No hop may rest on an application control alone."""
        for hop in policy["chain"]["hops"]:
            assert hop.get("networkControl"), f"{hop['id']} names no network control"

    def test_a_hop_without_an_application_control_says_so_explicitly(
        self, policy: dict[str, Any]
    ) -> None:
        """A hop with one control is a hop resting on reachability alone.

        That is currently true of exactly one hop — ``apim-to-backend``, whose application control
        is deferred (ADR 0008) — and this test exists so that it stays *exactly one* and stays
        *declared*. A hop that quietly loses its application control, with no ``deferred`` block
        and no ADR behind it, fails here rather than passing as though it never had one.
        """
        for hop in policy["chain"]["hops"]:
            if hop.get("applicationControl"):
                continue

            assert hop.get("applicationControlStatus") == "deferred", (
                f"{hop['id']} names no application control and does not declare one deferred. "
                "A hop silently resting on reachability alone is the failure this registry "
                "exists to make visible."
            )

            deferred = hop.get("deferred") or {}
            adr = deferred.get("adr")
            assert adr, f"{hop['id']} declares a deferred control but names no ADR"
            assert (ROOT / adr).is_file(), f"{hop['id']} names an ADR that does not exist: {adr}"
            assert deferred.get("replacedBy") is None, (
                f"{hop['id']} names a replacement for its deferred control. The deferral was "
                "explicitly not a licence to introduce one; see the ADR."
            )


# ---------------------------------------------------------------------------
# The contract, and the code that consumes it
# ---------------------------------------------------------------------------


class TestTheIdentityContractIsClosed:
    """Five headers, exactly. A sixth is a second identity derivation under another name."""

    def test_the_policy_and_this_service_agree_on_the_contract(
        self, policy: dict[str, Any]
    ) -> None:
        contract = policy["identityContract"]
        assert contract["closed"] is True
        assert len(contract["headers"]) == 5
        assert sorted(contract["headers"]) == sorted(IDENTITY_HEADERS)


# ---------------------------------------------------------------------------
# The rules the policy states about backend source
# ---------------------------------------------------------------------------


class TestBackendsNeverParseTokens:
    """Identity is derived exactly once. A second derivation point is the one nobody audits."""

    def test_no_production_module_imports_a_token_library(self, policy: dict[str, Any]) -> None:
        forbidden = policy["backendRules"]["neverParseTokens"]["forbiddenInProductionSource"]
        violations = []
        for path in _production_sources():
            source = path.read_text(encoding="utf-8")
            # Import statements only. A module docstring explaining that this platform parses no
            # token would otherwise trip the guard that exists to enforce it — and a guard that
            # punishes the explanation gets the explanation deleted.
            for line in source.splitlines():
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                for term in forbidden:
                    if term.lower() in stripped.lower():
                        violations.append(f"{path.name}: {stripped}")
        assert not violations, "production source imports a token library:\n  " + "\n  ".join(
            violations
        )


class TestNoDirectServiceToServicePath:
    """Every application API call traverses the edge and the Gateway (spec 13.4)."""

    def test_no_production_module_addresses_another_service_directly(
        self, policy: dict[str, Any]
    ) -> None:
        """A private peer route is a second path into a backend — one where identity is whatever
        the caller felt like sending, because no gateway re-established it.
        """
        forbidden = policy["backendRules"]["noDirectServiceToService"][
            "forbiddenInProductionSource"
        ]
        violations = []
        for path in _production_sources():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                for term in forbidden:
                    if term in code:
                        violations.append(f"{path.name}:{number} contains {term!r}")
        assert not violations, (
            "production source addresses another platform service directly:\n  "
            + "\n  ".join(violations)
        )


# ---------------------------------------------------------------------------
# The deployed shape the policy requires
# ---------------------------------------------------------------------------


class TestTheGatewayIsConfiguredToBeTheTrustBoundary:
    """Half this boundary lives in files no compiler reads."""

    def test_the_gateway_deletes_every_inbound_copy_of_the_contract(
        self, policy: dict[str, Any]
    ) -> None:
        """The anti-spoofing control at the edge, and now the only one of its kind.

        APIM deletes any inbound copy of the contract before validating anything, so a caller
        arriving from the internet cannot smuggle one through the gateway. The backend-side half —
        refusing a request that could not prove gateway provenance — is deferred (ADR 0008) and
        was not replaced, which makes this deletion load-bearing in a way it was not before.
        """
        global_policy = APIM / "global.inbound.xml"
        assert global_policy.is_file(), f"the APIM global policy is missing: {global_policy}"
        xml = global_policy.read_text(encoding="utf-8")

        missing = [
            header
            for header in policy["identityContract"]["headers"]
            if f'<set-header name="{header}" exists-action="delete" />' not in xml
        ]
        assert not missing, "the APIM global policy does not delete an inbound copy of: " + str(
            missing
        )

    def test_the_gateway_checks_the_front_door_identifier(self) -> None:
        """The AzureFrontDoor.Backend service tag admits *every* Azure customer's Front Door.

        An attacker provisions their own profile and points it at this origin, satisfying the
        network control. The FDID check is what makes the origin specific to this platform.
        """
        xml = (APIM / "global.inbound.xml").read_text(encoding="utf-8")
        assert "X-Azure-FDID" in xml
        # A named value, never a literal: a literal pins the policy to one environment.
        assert "{{front-door-id}}" in xml

    def test_every_audience_has_a_policy_that_derives_its_identity(
        self, policy: dict[str, Any]
    ) -> None:
        """One policy per audience is what makes "the surface decides" structural.

        There is no shared branch in which the customer path could read a role claim.
        """
        violations = []
        for audience in policy["audiences"]:
            file = APIM / f"{audience['id']}.v1.xml"
            if not file.is_file():
                violations.append(f"{audience['id']}: no APIM policy at {file}")
                continue
            xml = file.read_text(encoding="utf-8")
            if "<validate-azure-ad-token" not in xml:
                violations.append(
                    f"{audience['id']}: validates no token, so identity is never derived"
                )
            if f"<value>{audience['credentialClass']}</value>" not in xml:
                violations.append(
                    f"{audience['id']}: does not state the credential class "
                    f"{audience['credentialClass']!r}"
                )
        assert not violations, "an audience has no gateway policy:\n  " + "\n  ".join(violations)

    def test_the_workload_audience_refuses_a_delegated_credential(self) -> None:
        """A workload that could present a human's token could act with that human's authority
        while appearing in the audit record as a machine (spec 11.3).
        """
        xml = (APIM / "workload.v1.xml").read_text(encoding="utf-8")
        assert 'ContainsKey("scp")' in xml, (
            "the workload policy does not refuse a delegated token. `scp` is present only on a "
            "delegated credential, and its absence is the discriminator."
        )

    def test_the_customer_audience_never_reads_a_role_claim(self) -> None:
        """Any person acting on a customer surface is an end user, *including staff*.

        This is the one place a person could promote themselves by holding a role elsewhere, so the
        absence is asserted rather than reviewed.
        """
        xml = (APIM / "customer.v1.xml").read_text(encoding="utf-8")
        assert 'Claims["roles"]' not in xml
        assert "Synthia_Admins" not in xml
        assert "Synthia_Agents" not in xml
        assert "<value>end_user</value>" in xml


class TestNoBackendIsReachableAroundTheGateway:
    """The network half of the apim-to-backend hop, asserted against committed manifests."""

    def _manifests(self) -> list[Path]:
        manifests = sorted((ROOT / "build" / "docker" / "containerapps").glob("*.yaml"))
        assert manifests, "no container app manifests were found"
        return manifests

    def test_no_container_app_declares_external_ingress(self) -> None:
        """External ingress on an application container app *is* the bypass.

        It is one line in a YAML file that reviews well and deploys quietly.
        """
        violations = [
            manifest.name
            for manifest in self._manifests()
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.split("#", 1)[0].replace(" ", "") == "external:true"
        ]
        assert not violations, f"a container app declares external ingress: {violations}"

    def test_front_door_publishes_the_gateway_and_the_two_portals_and_nothing_else(self) -> None:
        """An origin that is neither the gateway nor a portal bundle would be a public route to a
        backend that looks, in the portal, like a routing entry — the cheapest possible bypass of
        the entire trust boundary.

        **An allow-list by name, not a count** (ADR-0009). A count passes a definition that swapped
        one origin for another, which is exactly the change worth catching.
        """
        file = ROOT / "build" / "infra" / "frontdoor" / "front-door.json"
        assert file.is_file(), f"the Front Door definition is missing: {file}"
        front_door = json.loads(file.read_text(encoding="utf-8"))

        groups = {group["name"]: group for group in front_door["originGroups"]}
        assert set(groups) == {"apim", "customer-portal", "staff-portal"}

        origins = {group_name: group["origins"] for group_name, group in groups.items()}
        assert [origin["name"] for origin in origins["apim"]] == ["apim-gateway"]
        assert [origin["name"] for origin in origins["customer-portal"]] == ["customer-portal-app"]
        assert [origin["name"] for origin in origins["staff-portal"]] == ["staff-portal-app"]

        # Private Link everywhere, so no target holds a public endpoint of its own — and the link
        # must NAME a resource, not merely be present as a key.
        for group_origins in origins.values():
            for origin in group_origins:
                link = origin.get("sharedPrivateLinkResource", {})
                assert link.get("privateLink"), (
                    f"{origin['name']} is reachable without Private Link"
                )

    def test_only_the_gateway_origin_serves_an_api_path(self) -> None:
        """The portals serve static files. One answering ``/api`` would reach the platform on a
        host APIM never saw, which is the bypass the single gateway exists to prevent.
        """
        file = ROOT / "build" / "infra" / "frontdoor" / "front-door.json"
        front_door = json.loads(file.read_text(encoding="utf-8"))

        for route in front_door["routes"]:
            if route["originGroup"] == "apim":
                continue
            for pattern in route["patternsToMatch"]:
                assert not pattern.startswith("/api"), (
                    f"edge route {route['name']!r} publishes {pattern!r} on a portal origin"
                )


# ---------------------------------------------------------------------------
# Cross-platform parity
# ---------------------------------------------------------------------------


class TestBothPlatformsEnforceTheSamePolicy:
    """A rule enforced on one stack and not the other decides where insecure code gets written."""

    def test_the_dotnet_enforcer_exists(self) -> None:
        """Its absence would mean this policy covers half the platform."""
        assert DOTNET_ENFORCER.is_file(), (
            "the .NET half of the edge trust rule is missing. Both deployables sit behind the same "
            "gateway; a rule that only binds RagCore is not a platform rule."
        )

    def test_the_dotnet_enforcer_reads_the_shared_registry(self) -> None:
        """Not a reimplementation of it — the same file, so the two cannot disagree."""
        source = DOTNET_ENFORCER.read_text(encoding="utf-8")
        assert "edge-trust.json" in source, (
            "the .NET enforcer does not read build/policy/edge-trust.json. Two hand-maintained "
            "lists drift, and the drift is invisible until the weaker one is the one that mattered."
        )
