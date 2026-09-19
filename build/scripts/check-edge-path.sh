#!/usr/bin/env bash
#
# Edge path check (constitution Principle I, spec 10.3/13.4, build/policy/edge-trust.json).
#
# All public API traffic traverses Front Door + WAF, then APIM, then the backend. APIM is the
# identity/trust boundary and the only place a token is validated. This script guards the parts of
# that arrangement that live in committed configuration rather than in code:
#
#   1. No container app publishes external ingress.
#   2. The APIM global policy deletes every inbound copy of the identity contract.
#   3. The APIM global policy checks this platform's Front Door identifier.
#   4. Every audience has a gateway policy that validates a token.
#   5. Front Door publishes exactly three origins — the gateway and the two portal bundles — each
#      over Private Link, and only the gateway one serves /api (ADR-0009).
#   6. Neither deployable addresses the other by an internal address.
#
# WHAT THIS GUARD NO LONGER CHECKS, deliberately. The apim-to-backend hop used to carry a client
# certificate: ingress required it, APIM attached it by certificate-id, the APIM identity could
# read it from Key Vault, and its expiry was alerted. That mechanism is DEFERRED in full - see
# docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md - and nothing replaced
# it. The checks that enforced it are gone rather than softened, because a guard that passes
# vacuously is worse than no guard: it is a guard somebody has already stopped reading.
#
# WHY A SHELL GUARD WHEN BOTH STACKS ALREADY TEST THIS. The in-language suites are the detailed
# enforcement and they are better at it - they parse, they read the shared policy, they pose the
# attack against the real pipeline. This runs in seconds, needs no toolchain, and covers the case
# where somebody edits a YAML or XML file in a change that touches no code and therefore runs
# neither test suite. That is the change most likely to open the boundary.
#
# Implementation note, inherited from check-boundaries.sh and learned the same way: plain `find` +
# `grep` only, and THIS GUARD MUST NOT FIRE ON PROSE. Every check below either anchors at markup
# position or strips comments, because a guard that flags the comment explaining the rule is a
# guard that gets suppressed - and then the rule has nothing behind it at all.
#
# Exit 0 = the edge path is intact. Exit 1 = violation(s), with the offending lines printed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

POLICY="build/policy/edge-trust.json"
APIM="build/infra/apim"
MANIFESTS="build/docker/containerapps"
FRONTDOOR="build/infra/frontdoor/front-door.json"

violations=0

fail() {
  printf '\n  \xe2\x9c\x97 %s\n' "$1"
  [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/      /'
  violations=$((violations + 1))
}

pass() {
  printf '  \xe2\x9c\x93 %s\n' "$1"
}

require_file() {
  if [ ! -f "$1" ]; then
    fail "$2 is missing: $1"
    return 1
  fi
  return 0
}

echo "Checking the edge path (Front Door -> APIM -> backend)..."

# ---------------------------------------------------------------- the registry itself
#
# Checked first and separately. Every rule below is a restatement of something this file declares,
# so its absence does not make the platform safe - it makes the platform unguarded while every
# other check still reports success.
require_file "$POLICY" "The shared edge trust policy" || {
  printf '\nEdge path check FAILED: the policy both stacks read is missing.\n'
  exit 1
}

# ------------------------------------------------- (1) no backend is publicly reachable
#
# THE SINGLE MOST IMPORTANT LINE IN THIS SCRIPT. External ingress on an application container app
# is a public route straight to a backend, bypassing the WAF, the gateway and the only place
# identity is derived. It is one word in a YAML file and it reviews as a formatting change.
if [ -d "$MANIFESTS" ]; then
  hits="$(find "$MANIFESTS" -type f -name '*.yaml' -print 2>/dev/null \
    | tr '\n' '\0' | xargs -0 grep -nE '^[[:space:]]*external:[[:space:]]*true' 2>/dev/null)"
  if [ -n "$hits" ]; then
    fail "A container app declares external ingress - a path around APIM" "$hits"
  else
    pass "No container app publishes external ingress."
  fi
else
  fail "No container app manifests were found under $MANIFESTS"
fi

# --------------------------------- (3) the gateway strips every inbound copy of the contract
#
# The other end of the anti-spoofing control. The backend refuses a request that cannot prove
# provenance; APIM deletes any inbound copy of the contract before it validates anything. Neither
# is sufficient alone, and this is the half no compiler and no unit test would otherwise reach.
#
# The header list is read from the policy rather than repeated here, so a sixth header cannot be
# added to the contract without this check demanding it be stripped too.
GLOBAL_POLICY="$APIM/global.inbound.xml"
if require_file "$GLOBAL_POLICY" "The APIM global policy"; then
  headers="$(grep -oE '"X-Idp-[A-Za-z-]+"' "$POLICY" | tr -d '"' | sort -u)"

  if [ -z "$headers" ]; then
    fail "The policy declares no identity contract headers - the contract cannot be empty"
  else
    missing=""
    while IFS= read -r header; do
      [ -n "$header" ] || continue
      if ! grep -qF "<set-header name=\"$header\" exists-action=\"delete\" />" "$GLOBAL_POLICY"; then
        missing="${missing}${header}"$'\n'
      fi
    done <<EOF
$headers
EOF
    if [ -n "$missing" ]; then
      fail "The APIM global policy does not delete an inbound copy of these headers" "$missing"
    else
      pass "APIM deletes every inbound copy of the identity contract."
    fi
  fi

  # ------------------------------------------ (4) the origin is specific to this platform
  #
  # The AzureFrontDoor.Backend service tag admits EVERY Azure customer's Front Door, so an attacker
  # provisions their own profile and points it at this origin. The FDID check is what makes the
  # origin this platform's rather than anyone's.
  if grep -qF 'X-Azure-FDID' "$GLOBAL_POLICY" && grep -qF '{{front-door-id}}' "$GLOBAL_POLICY"; then
    pass "APIM checks this platform's Front Door identifier."
  else
    fail "The APIM global policy does not check X-Azure-FDID against the {{front-door-id}} named value"
  fi
fi

# ------------------------------------------------ (5) every audience derives identity at APIM
#
# One policy per audience is what makes "the surface decides which authorization model applies"
# structural rather than remembered: there is no shared branch in which the customer path could
# read a role claim.
missing=""
for audience in customer staff workload; do
  file="$APIM/$audience.v1.xml"
  if [ ! -f "$file" ]; then
    missing="${missing}${audience}: no policy at ${file}"$'\n'
  elif ! grep -qF '<validate-azure-ad-token' "$file"; then
    missing="${missing}${audience}: validates no token, so identity is never derived"$'\n'
  fi
done
if [ -n "$missing" ]; then
  fail "An audience has no gateway policy deriving its identity" "$missing"
else
  pass "Every audience derives identity at the gateway."
fi

# ------------------------------------- (6) Front Door fronts the gateway and the portals, only
#
# An origin that is neither the gateway nor a portal bundle would be a public route to a backend
# that looks, in the portal, like a routing entry. It is the cheapest possible bypass of the entire
# trust boundary, so the check is an allow-list rather than a count (ADR-0009).
if require_file "$FRONTDOOR" "The Front Door definition"; then
  # AN ALLOW-LIST BY NAME, not a count. The edge fronts the gateway and the two portal bundles
  # (ADR-0009) — three origin groups, no more, and a fourth is the cheapest possible bypass
  # whatever it is called. Counting host names would pass a definition that swapped one origin for
  # another, which is precisely the change worth catching.
  #
  # ONLY THE GATEWAY GROUP SERVES AN API. The portal groups serve static files from container apps
  # that hold no data, no secret and no identity; see the route check below, which is the half that
  # stops one of them being given an /api path.
  # The JSON is read with an interpreter rather than grep: "which origin group does this route
  # target" is a structural question, and a grep that answered it would be answering a different,
  # easier one. `python` or `python3`, whichever this machine has — CI is Linux, developers here
  # are on Windows, and the guard must fail for a real reason on both.
  PYTHON="$(command -v python3 || command -v python || true)"
  if [ -z "$PYTHON" ]; then
    fail "No python on PATH; the Front Door checks cannot read the definition"
  fi

  expected_groups="apim customer-portal staff-portal"
  actual_groups="$("$PYTHON" "build/scripts/edge_front_door.py" groups "$FRONTDOOR")"
  private="$("$PYTHON" "build/scripts/edge_front_door.py" public-origins "$FRONTDOOR")"
  api_on_a_portal="$("$PYTHON" "build/scripts/edge_front_door.py" api-on-portal "$FRONTDOOR")"

  if [ "$actual_groups" != "$expected_groups" ]; then
    fail "The Front Door origin groups are '$actual_groups'; expected exactly '$expected_groups'"
  elif [ -n "$private" ]; then
    fail "A Front Door origin does not reach its target over Private Link, so that target holds a public endpoint" "$private"
  elif [ -n "$api_on_a_portal" ]; then
    # A portal host answering /api would be a public path to the platform on a host APIM never
    # saw — the bypass the single gateway exists to prevent, wearing the costume of a routing entry.
    fail "A portal route publishes an /api path, which would reach the platform without the gateway" "$api_on_a_portal"
  else
    pass "Front Door fronts the gateway and the two portals, each privately, and only the gateway serves /api."
  fi
fi

# ------------------------------------------- (7) no service addresses another service directly
#
# Specification 13.4: every application API call traverses the edge and the Gateway. A private peer
# route is a second path into a backend - one where identity is whatever the caller felt like
# sending, because no gateway re-established it.
#
# Scoped to production source, with whole-line comments dropped, so the modules that document this
# rule are not the ones that trip it.
hits="$(find dotnet/src ragcore/src -type f \( -name '*.cs' -o -name '*.py' \) \
  \( -path '*/bin/*' -o -path '*/obj/*' -o -path '*/__pycache__/*' \) -prune -o \
  -type f \( -name '*.cs' -o -name '*.py' \) -print 2>/dev/null \
  | tr '\n' '\0' \
  | xargs -0 grep -nIE '\.internal\.azurecontainerapps\.io' 2>/dev/null \
  | grep -vE '^[^:]+:[0-9]+:[[:space:]]*(//|\*|#)')"
if [ -n "$hits" ]; then
  fail "Production source addresses another service by its internal address" "$hits"
else
  pass "No service addresses another by its internal address."
fi

# ---------------------------------------------------------------- result
if [ "$violations" -gt 0 ]; then
  printf '\nEdge path check FAILED with %d violation(s).\n' "$violations"
  echo "All public API traffic traverses Front Door + WAF, then APIM, then the backend, and APIM is"
  echo "the only place identity is derived (constitution Principle I). A backend reachable around"
  echo "that path is a backend whose identity headers anybody can write."
  echo ""
  echo "The rules are declared once, in $POLICY. If one of them is genuinely wrong, amend that file"
  echo "and both enforcers - not this script alone."
  exit 1
fi

printf '\nEdge path intact.\n'
exit 0
