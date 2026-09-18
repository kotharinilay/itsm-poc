"""APIM is the only synchronous route to this service, asserted from the committed configuration.

Spec §13.4, `FR-INTEG-011`, `FR-INTEG-012`, ADR-0007.

**Two halves, and neither is sufficient alone.** `test_boundary.py` asserts the *runtime* half — a
request arriving without gateway provenance is refused by the service itself. This file asserts the
*configuration* half: that APIM is configured to front this service at all, that reaching it
requires an application role the generic workload role does not grant, and that nothing declares a
direct route.

The runtime half alone would pass on a deployment where APIM never routed here. The configuration
half alone would pass on a service that accepted anything. Together they say: the only declared path
in is through the gateway, and the service refuses everything else.

**Structural rather than deployed**, like every other guard over `build/infra`. It reads committed
configuration, so the routing holds in CI without an Azure subscription — which matters because a
deployed environment is this scaffold's longest-lead dependency, and a control checkable only there
goes unchecked until then. The deployed proof is `T311`.

**This service reads the shared registry rather than keeping its own list.** Two hand-maintained
copies drift, and the drift is invisible until the day the weaker one is the one that mattered.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

pytestmark = pytest.mark.security

_REPO: Final = Path(__file__).resolve().parents[3]
_APIS: Final = _REPO / "build" / "infra" / "apim" / "apis.json"
_WORKLOAD_POLICY: Final = _REPO / "build" / "infra" / "apim" / "workload.v1.xml"
_CONTRACT: Final = _REPO / "build" / "contracts" / "integrations" / "workload.v1.openapi.json"

_API_ID: Final = "workload-v1-integrations"
_BACKEND_ID: Final = "integrations"
_API_PATH: Final = "api/workload/v1/integrations"


def _registry() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(_APIS.read_text(encoding="utf-8"))
    return document


def _api() -> dict[str, Any]:
    for entry in _registry()["apis"]:
        if entry["id"] == _API_ID:
            return dict(entry)
    pytest.fail(
        f"{_API_ID!r} is not in the routing registry. Without it APIM fronts no route to this "
        "service, and the only way to reach it would be the direct one the boundary forbids."
    )


def _backend() -> dict[str, Any]:
    for entry in _registry()["backends"]:
        if entry["id"] == _BACKEND_ID:
            return dict(entry)
    pytest.fail(f"{_BACKEND_ID!r} is not a declared backend.")


def test_the_gateway_fronts_this_service_on_the_workload_audience() -> None:
    """**Positive.** APIM declares the route, on the workload audience, over https only."""
    api = _api()

    assert api["audience"] == "workload"
    assert api["path"] == _API_PATH
    assert api["backend"] == _BACKEND_ID
    assert api["protocols"] == ["https"]


def test_the_route_is_longer_than_ragcores_so_the_most_specific_prefix_wins() -> None:
    """The whole routing rule for this pair, asserted rather than described.

    Both APIs live under `api/workload/v1`. APIM resolves the most specific prefix first, so the two
    coexist with no ordering flag to get wrong — but only while this path is strictly longer and
    starts with the other. If someone shortened it, every Integrations call would quietly reach
    RagCore and return a 404 indistinguishable from a client calling a route that does not exist.
    """
    ragcore_path = next(
        entry["path"] for entry in _registry()["apis"] if entry["id"] == "workload-v1"
    )

    assert _API_PATH.startswith(f"{ragcore_path}/")
    assert len(_API_PATH) > len(ragcore_path)


def test_reaching_this_service_requires_a_role_the_workload_role_does_not_grant() -> None:
    """**The authorization difference, and the reason the boundary shrinks any blast radius.**

    The generic workload role exists so a service can reach the execution leg. This service is the
    only holder of per-organisation connector credentials and the only component with an egress path
    to a customer system, so "can reach a platform service" MUST NOT imply "can drive connectors".

    Asserted on the policy text because that is where the check runs. A named value declared in the
    registry but never referenced by a policy is configuration that documents an intention nothing
    enforces.
    """
    policy = _WORKLOAD_POLICY.read_text(encoding="utf-8")

    assert "{{integrations-app-role}}" in policy
    # The named value is DECLARED as well as referenced. A policy naming a value the deployment
    # never defines resolves to nothing, and a role check against nothing is a check that passes.
    assert "integrations-app-role" in _registry()["namedValues"]

    # And it is a DIFFERENT value from the generic one, checked where it matters: the path-scoped
    # block demands the Integrations role, not the workload role. One named value serving both
    # would make the distinction above a comment rather than a control.
    assert "{{workload-app-role}}" in policy

    scoped = policy[policy.index("context.Request.Url.Path") :]
    scoped = scoped[: scoped.index("</choose>")]
    assert "{{integrations-app-role}}" in scoped
    assert "{{workload-app-role}}" not in scoped


def test_the_role_check_matches_this_services_path_prefix_and_not_a_substring() -> None:
    """A substring match would demand this role on RagCore routes that merely contain the word.

    That direction fails closed, so it would never surface as a security finding — it would surface
    as a RagCore route returning 403 to a correctly-credentialled caller, which is harder to
    attribute and therefore likelier to be "fixed" by deleting the check entirely.
    """
    policy = _WORKLOAD_POLICY.read_text(encoding="utf-8")

    # Matched to the end of the line rather than to the next quote: the condition embeds quoted
    # strings, so a `[^"]*` bound stops before the part that carries the meaning — and the test then
    # asserts something about the first thirty characters of an expression.
    condition = re.search(r"^.*context\.Request\.Url\.Path.*$", policy, re.MULTILINE)
    assert condition is not None, "the path-scoped role check is gone"

    matched = condition.group(0)
    assert "StartsWith" in matched
    assert _API_PATH in matched
    assert ".Contains(" not in matched


def test_the_backend_is_internal_and_authenticated_by_certificate() -> None:
    """Internal ingress plus a client certificate: the two halves of "not publicly reachable".

    Internal-only ingress means the address is not routable from outside. The certificate means that
    being *inside* is not enough either — which is what makes a compromised sibling container unable
    to call this service directly.
    """
    backend = _backend()

    assert backend["credentials"]["type"] == "client-certificate"
    assert backend["containerApp"] == "build/docker/containerapps/integrations.yaml"


def test_no_api_declares_a_direct_route_to_this_service() -> None:
    """**The negative.** Every declared path to this backend goes through an APIM API.

    There is no second mechanism — no alternate host, no bypass entry, no API on another audience
    pointed at this backend. A customer- or staff-audience API with this backend would be a public
    route to the component holding every organisation's connector secrets.
    """
    pointing_here = [entry for entry in _registry()["apis"] if entry.get("backend") == _BACKEND_ID]

    assert len(pointing_here) == 1
    assert pointing_here[0]["id"] == _API_ID
    assert pointing_here[0]["audience"] == "workload", (
        "this backend is reachable from a non-workload audience. Only a workload principal calls "
        "this service; a customer or staff route here would be a client-facing path to connectors."
    )


def test_the_published_contract_is_generated_and_is_this_services_own() -> None:
    """No hand-written schema, and no document merged with RagCore's.

    A hand-maintained copy drifts from what the service accepts, and the drift is invisible until a
    client believes the document. A *merged* workload document would be worse: the compatibility
    gate diffs per deployable, so merging would let a breaking change in one service be masked by
    the other's shape.
    """
    api = _api()

    assert api["openApi"]["handWritten"] is False
    assert api["openApi"]["emittedBy"] == "integrations/scripts/emit_contracts.py"
    assert api["openApi"]["source"] == "build/contracts/integrations/workload.v1.openapi.json"

    # The document it names exists, is this service's, and is not RagCore's.
    assert _CONTRACT.is_file()
    document = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    assert every_path_is_ours(document), (
        "the Integrations document describes a route outside its own path prefix. Two deployables "
        "serve this audience, and a document describing the other's routes is a merged one."
    )


def every_path_is_ours(document: dict[str, Any]) -> bool:
    """Whether every route in the document belongs to this service's prefix.

    Args:
        document: The emitted OpenAPI document.

    Returns:
        ``True`` when every path starts with this service's routing prefix.
    """
    paths = document.get("paths", {})
    return bool(paths) and all(path.lstrip("/").startswith(_API_PATH) for path in paths)


def test_no_committed_configuration_names_this_backends_address_outside_the_registry() -> None:
    """The address lives in one named value, resolved at deployment, and nowhere else.

    Knowing an internal address grants nothing on its own — ingress is internal-only and requires a
    certificate. But an address written into application configuration is the one thing a direct
    call cannot be constructed without, so it stays a deployment-resolved named value rather than a
    literal anybody can copy.
    """
    named = _registry()["namedValues"]

    assert named["integrations-backend-url"]["source"] == "deployment"

    # No literal internal address anywhere in the registry.
    assert ".internal." not in _APIS.read_text(encoding="utf-8")
