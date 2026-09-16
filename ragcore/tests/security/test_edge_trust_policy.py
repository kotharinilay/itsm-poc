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
construct rather than surfacing as a 403 in an environment somebody has to reproduce. The
behavioural half lives in ``test_gateway_provenance.py``, which poses the attack against the real
pipeline.

**Why the infrastructure is asserted at all.** Half of this boundary lives outside the application —
in an APIM policy, a Front Door definition, an ingress manifest — where no compiler and no unit test
would otherwise look. Those are also the files where a one-line change (``external: true``, a
deleted ``set-header``) reviews well and deploys quietly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

from ragcore.api.middleware.provenance import (
    EXEMPT_PATH_PREFIXES,
    FORWARDED_CLIENT_CERT_HEADER,
)
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


class TestEveryHopHasTwoIndependentControls:
    """ "Neither control is sufficient alone" (spec 10.3) is a claim about *pairs*."""

    def test_the_chain_is_client_to_front_door_to_apim_to_backend(
        self, policy: dict[str, Any]
    ) -> None:
        """The three hops, in order, with nothing between them."""
        assert [hop["id"] for hop in policy["chain"]["hops"]] == [
            "client-to-frontdoor",
            "frontdoor-to-apim",
            "apim-to-backend",
        ]

    def test_every_hop_names_both_a_network_and_an_application_control(
        self, policy: dict[str, Any]
    ) -> None:
        """A hop with one control is a hop resting on reachability alone.

        That was the state this whole arrangement was written to fix: the backends could not
        distinguish an APIM-stamped identity header from one a caller typed, and said so in their
        own comments.
        """
        for hop in policy["chain"]["hops"]:
            assert hop.get("networkControl"), f"{hop['id']} names no network control"
            assert hop.get("applicationControl"), f"{hop['id']} names no application control"


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

    def test_the_provenance_header_this_service_reads_is_the_one_the_policy_names(
        self, policy: dict[str, Any]
    ) -> None:
        """Two ends of one wire.

        If APIM stamps a header this service does not read, every request is refused; if this
        service reads one APIM does not stamp, nothing is checked. The second failure is silent,
        which is why it is asserted rather than trusted.
        """
        assert policy["gatewayCertificate"]["forwardedAs"] == FORWARDED_CLIENT_CERT_HEADER

    def test_the_exempt_paths_this_service_serves_are_the_ones_the_policy_names(
        self, policy: dict[str, Any]
    ) -> None:
        """The exemption list is the softest part of the arrangement, so it is pinned hardest."""
        assert tuple(policy["provenanceExempt"]["pathPrefixes"]) == EXEMPT_PATH_PREFIXES


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
        """The other end of the anti-spoofing control.

        This service refuses a request that cannot prove provenance; APIM deletes any inbound copy
        of the contract before validating anything. Neither is sufficient alone.
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

        # The forwarded certificate is the more dangerous of the two: a caller who could set it
        # would be asserting gateway provenance itself, which every other control rests on.
        assert f'<set-header name="{FORWARDED_CLIENT_CERT_HEADER}" exists-action="delete" />' in xml

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

    def test_every_container_app_serving_ingress_requires_a_client_certificate(self) -> None:
        """Internal ingress alone admits everything already inside the VNet.

        ``accept`` is specifically not enough: it forwards a certificate when one is offered and
        nothing when one is not, so an unauthenticated caller looks exactly like a correctly
        configured one that has not been given a certificate yet.

        **Scoped to apps that serve ingress.** A worker — a Service Bus consumer, a sweep — dials
        *out* over AMQP as a managed identity and accepts no inbound request, so there is no
        connection for a client certificate to appear on. Requiring it there would fail the first
        correctly written worker manifest, and a rule that fires on correct code is one that gets
        skipped.
        """
        violations = []
        for manifest in self._manifests():
            code = [
                line.split("#", 1)[0].strip()
                for line in manifest.read_text(encoding="utf-8").splitlines()
            ]
            if "ingress:" not in code:
                continue
            if "clientCertificateMode: require" not in code:
                violations.append(manifest.name)
        assert not violations, (
            f"a container app serving ingress does not require a client certificate: {violations}"
        )

    def test_the_gateway_certificate_is_referenced_in_a_way_that_survives_rotation(self) -> None:
        """A Key Vault certificate's thumbprint **changes** when it is rotated.

        An APIM policy identifying it by thumbprint silently fails to resolve the new one — it stops
        attaching a client certificate at all. There is no error at the gateway; it surfaces as
        every backend call losing provenance at the same moment.

        Asserted rather than reviewed because the broken spelling is the one that looks more
        precise, and because it works perfectly until the day it does not.
        """
        xml = (APIM / "global.inbound.xml").read_text(encoding="utf-8")
        assert "<authentication-certificate thumbprint=" not in xml
        assert "<authentication-certificate certificate-id=" in xml

    def test_rotation_is_deliberate_and_expiry_is_monitored(self, policy: dict[str, Any]) -> None:
        """These two are adopted together or not at all.

        Pinning the Key Vault version stops an automatic four-hour sync from rotating the
        certificate out from under a backend allow-list that pins the leaf hash — an unattended,
        total outage with no deployment behind it.

        But pinning the version also means nothing renews the certificate on our behalf any more,
        which turns expiry from a background concern into the residual risk of the whole design. A
        policy declaring one without the other is declaring half a control.
        """
        certificate = policy["gatewayCertificate"]
        rotation = certificate["rotation"]

        assert rotation["strategy"] == "pinned-version"
        assert rotation["automaticSyncDisabled"] is True

        runbook = ROOT / rotation["runbook"]
        assert runbook.is_file(), (
            f"the rotation runbook is missing: {runbook}. Rotation here is a sequenced manual "
            "release — widen the allow-list, then switch the certificate — and the order IS the "
            "control. An unwritten sequence is one somebody performs backwards under pressure."
        )

        expiry = certificate["expiryMonitoring"]
        assert expiry["required"] is True
        assert expiry["alertLeadTimeDays"] >= 30

    def test_expiry_monitoring_is_provisioned_and_not_merely_declared(
        self, policy: dict[str, Any]
    ) -> None:
        """A policy declaring monitoring that infrastructure does not provide is worse than neither.

        The declaration is what stops somebody checking. This asserts the alerting exists as
        committed infrastructure, not as an intention.
        """
        expiry = policy["gatewayCertificate"]["expiryMonitoring"]
        alerts = ROOT / expiry["definedIn"]
        assert alerts.is_file(), f"the expiry alerting is missing: {alerts}"

        alerting = json.loads(alerts.read_text(encoding="utf-8"))

        event_types: list[str] = []
        unpaged: list[str] = []
        for subscription in alerting["eventSubscriptions"]:
            event_types.extend(subscription["filter"]["includedEventTypes"])
            # An alert nobody is paged by is a dashboard.
            if not subscription["destination"]["properties"].get("actionGroups"):
                unpaged.append(subscription["name"])

        assert "Microsoft.KeyVault.CertificateNearExpiry" in event_types
        assert "Microsoft.KeyVault.CertificateExpired" in event_types
        assert not unpaged, f"an expiry alert reaches no action group: {unpaged}"

    def test_the_paging_lead_time_is_recorded_separately_from_the_earliest_notice(
        self, policy: dict[str, Any]
    ) -> None:
        """Two lead times, because Azure gives us no choice.

        The certificate near-expiry event is fixed at 30 days and exposes no setting; only the
        *key* near-expiry event is configurable. So the earliest we can be **told** is 45 days, by
        a Key Vault lifetime action, over email — and the earliest we can be **woken** is 30.

        Both are recorded because collapsing them to the friendlier number would be a lie an
        operator plans around: email is the weaker mechanism, and one holiday period consumes the
        whole difference. The 30-day page is the real deadline.
        """
        expiry = policy["gatewayCertificate"]["expiryMonitoring"]

        paging = expiry["pagingLeadTimeDays"]
        assert paging >= 30
        assert expiry["alertLeadTimeDays"] >= paging

        channels = expiry["channels"]
        assert any(channel["pages"] for channel in channels)
        assert any(channel["leadTimeDays"] == 0 and channel["pages"] for channel in channels), (
            "expiry itself must page: by then it is an outage and the cause must be named at once"
        )

    def test_front_door_publishes_exactly_one_origin_and_it_is_the_gateway(self) -> None:
        """A second origin would be a public route to a backend that looks, in the portal, like a
        routing entry. It is the cheapest possible bypass of the entire trust boundary.
        """
        file = ROOT / "build" / "infra" / "frontdoor" / "front-door.json"
        assert file.is_file(), f"the Front Door definition is missing: {file}"
        front_door = json.loads(file.read_text(encoding="utf-8"))

        groups = front_door["originGroups"]
        assert len(groups) == 1
        origins = groups[0]["origins"]
        assert len(origins) == 1
        assert origins[0]["name"] == "apim-gateway"
        # Private Link, so APIM itself has no public ingress at all.
        assert "sharedPrivateLinkResource" in origins[0]


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

    def test_both_deployables_enforce_provenance_in_their_own_pipeline(self) -> None:
        """A shared policy file proves nothing if only one side acts on it.

        Asserted against the middleware registration rather than the middleware's existence: a
        module that exists but is never added to the pipeline is the exact shape of a control
        somebody refactored out.
        """
        ragcore_app = (ROOT / "ragcore" / "src" / "ragcore" / "api" / "app.py").read_text(
            encoding="utf-8"
        )
        assert "GatewayProvenanceMiddleware" in ragcore_app

        dotnet_program = (ROOT / "dotnet" / "src" / "Synthia.Api" / "Program.cs").read_text(
            encoding="utf-8"
        )
        assert "UseMiddleware<GatewayProvenanceMiddleware>()" in dotnet_program

    def test_provenance_runs_before_identity_on_both_stacks(self) -> None:
        """Order is part of the control.

        The identity contract is trusted precisely and only because APIM set it, so a request that
        did not come through APIM must be refused before any part of that contract is read.
        Starlette applies middleware outermost-last, so on the RagCore side provenance must be
        added *after* identity to run *before* it.
        """
        ragcore_app = (ROOT / "ragcore" / "src" / "ragcore" / "api" / "app.py").read_text(
            encoding="utf-8"
        )
        # Matched on the registrations rather than on the names, which also appear in the imports
        # above them — an ordering assertion that can be satisfied by an import statement asserts
        # nothing about the pipeline.
        registrations = re.findall(r"app\.add_middleware\(\s*([A-Za-z]+)", ragcore_app)
        assert registrations.index("IdentityHeaderMiddleware") < registrations.index(
            "GatewayProvenanceMiddleware"
        ), "on Starlette, provenance must be added after identity in order to run before it"
        assert registrations.index("GatewayProvenanceMiddleware") < registrations.index(
            "CorrelationIdMiddleware"
        ), "correlation must remain outermost, so even a refused request is correlatable"

        dotnet_program = (ROOT / "dotnet" / "src" / "Synthia.Api" / "Program.cs").read_text(
            encoding="utf-8"
        )
        assert dotnet_program.index(
            "UseMiddleware<GatewayProvenanceMiddleware>()"
        ) < dotnet_program.index("UseMiddleware<IdentityContextMiddleware>()"), (
            "on ASP.NET Core, middleware runs in registration order, so provenance must be "
            "registered before identity"
        )

    def test_both_allow_list_settings_are_declared(self, policy: dict[str, Any]) -> None:
        """One name per stack, documented in the policy the deployment pipeline reads."""
        settings = policy["gatewayCertificate"]["allowListSetting"]
        assert set(settings) == {"dotnet", "ragcore"}
        assert settings["ragcore"] == "SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS"
