#!/usr/bin/env bash
#
# Edge path check (constitution Principle I, spec 10.3/13.4, build/policy/edge-trust.json).
#
# All public API traffic traverses Front Door + WAF, then APIM, then the backend. APIM is the
# identity/trust boundary and the only place a token is validated. This script guards the parts of
# that arrangement that live in committed configuration rather than in code:
#
#   1. No container app publishes external ingress.
#   2. Every container app requires the gateway client certificate.
#   3. The APIM global policy deletes every inbound copy of the identity contract.
#   4. The APIM global policy checks this platform's Front Door identifier.
#   5. Every audience has a gateway policy that validates a token.
#   6. Front Door publishes exactly one origin, and it is APIM.
#   7. Neither deployable addresses the other by an internal address.
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

# ------------------------------------------- (2) every backend demands gateway provenance
#
# The network control admits everything already inside the VNet. The certificate is what narrows
# that to APIM. `accept` is specifically not enough - it forwards a certificate when one is offered
# and nothing when one is not, so an unauthenticated caller is indistinguishable from a correctly
# configured one that has not been given a certificate yet.
#
# SCOPED TO APPS THAT ACTUALLY SERVE INGRESS. A worker - the Service Bus consumers, the sweeps -
# has no ingress block at all: it dials OUT to Service Bus over AMQP as a managed identity and
# accepts no inbound request, so there is no connection for a client certificate to appear on.
# Demanding the setting there would be a guard that fails the first correctly-written worker
# manifest somebody adds, and a guard that cries wolf on correct code is one that gets bypassed.
#
# The condition is "declares ingress", not "is named like an API", so a worker that later grows an
# ingress block is covered from the moment it does.
if [ -d "$MANIFESTS" ]; then
  missing=""
  while IFS= read -r manifest; do
    [ -n "$manifest" ] || continue
    grep -qE '^[[:space:]]*ingress:[[:space:]]*$' "$manifest" || continue
    if ! grep -qE '^[[:space:]]*clientCertificateMode:[[:space:]]*require[[:space:]]*$' "$manifest"; then
      missing="${missing}${manifest}"$'\n'
    fi
  done <<EOF
$(find "$MANIFESTS" -type f -name '*.yaml' 2>/dev/null)
EOF
  if [ -n "$missing" ]; then
    fail "A container app serving ingress does not require the gateway client certificate" "$missing"
  else
    pass "Every container app serving ingress requires a gateway client certificate."
  fi
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
    # The forwarded certificate is the more dangerous of the two: a caller who could set it would
    # be asserting gateway provenance itself, which every other control here rests on.
    if ! grep -qF '<set-header name="X-Forwarded-Client-Cert" exists-action="delete" />' "$GLOBAL_POLICY"; then
      missing="${missing}X-Forwarded-Client-Cert"$'\n'
    fi

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

  # ------------------------- (4b) the client certificate is referenced in a way that survives
  #
  # A Key Vault certificate's thumbprint CHANGES when it is rotated, and an APIM policy that
  # identifies it by thumbprint silently fails to resolve the new one - it stops attaching a client
  # certificate at all. There is no error at the gateway; it surfaces as every backend call losing
  # provenance simultaneously.
  #
  # This is checked here rather than left to review because the wrong spelling is the one that
  # looks more precise, and because it works perfectly until the day it doesn't.
  if grep -qE '<authentication-certificate[^>]*thumbprint=' "$GLOBAL_POLICY"; then
    fail "The APIM policy identifies the client certificate by thumbprint" \
      "A Key Vault certificate's thumbprint changes on rotation and the policy will silently stop
resolving it. Use certificate-id, which names the APIM entity and survives rotation."
  elif grep -qE '<authentication-certificate[^>]*certificate-id=' "$GLOBAL_POLICY"; then
    pass "The client certificate is referenced by certificate-id, which survives rotation."
  else
    fail "The APIM global policy attaches no client certificate to the backend connection"
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

# ------------------------------------------------------ (6) Front Door fronts only the gateway
#
# A second origin would be a public route to a backend that looks, in the portal, like a routing
# entry. It is the cheapest possible bypass of the entire trust boundary.
if require_file "$FRONTDOOR" "The Front Door definition"; then
  origin_count="$(grep -cE '^[[:space:]]*"hostName":' "$FRONTDOOR")"
  if [ "$origin_count" -ne 2 ]; then
    # Two: the endpoint's own hostname and the single origin's. Any more means another origin or
    # another endpoint, and both are new public surface.
    fail "The Front Door definition declares $origin_count host names; expected exactly 2 (one endpoint, one origin)"
  elif ! grep -qF '"sharedPrivateLinkResource"' "$FRONTDOOR"; then
    fail "The Front Door origin does not reach APIM over Private Link, so APIM holds a public endpoint"
  else
    pass "Front Door fronts exactly one origin, and reaches it privately."
  fi
fi

# ------------------------------------------- (6b) expiry of the gateway certificate is alerted
#
# The control that makes the pinned-version rotation strategy safe. Automatic Key Vault sync into
# APIM is deliberately off, so nothing moves this certificate on our behalf - expiry is the
# residual risk of the whole edge design.
#
# Checked here because the failure it guards against is uniquely misleading: on expiry every
# application request fails 403 on both deployables while health probes keep passing, so replicas
# stay green and in rotation with no deployment in the window to correlate against.
#
# Asserted against the infrastructure rather than against the policy's claim to have it. A policy
# that declares monitoring and infrastructure that does not provide it is worse than neither,
# because the declaration is what stops somebody checking.
EXPIRY_ALERTS="build/infra/monitoring/gateway-certificate-expiry.json"
if require_file "$EXPIRY_ALERTS" "The gateway certificate expiry alerting"; then
  missing=""
  for event in CertificateNearExpiry CertificateExpired; do
    if ! grep -qF "Microsoft.KeyVault.$event" "$EXPIRY_ALERTS"; then
      missing="${missing}Microsoft.KeyVault.${event}"$'\n'
    fi
  done

  # An alert nobody is paged by is a dashboard. Both of the above must reach an action group.
  if ! grep -qF '"actionGroups"' "$EXPIRY_ALERTS"; then
    missing="${missing}no actionGroups - the alerts notify nobody"$'\n'
  fi

  if [ -n "$missing" ]; then
    fail "The gateway certificate expiry alerting does not cover" "$missing"
  else
    pass "Gateway certificate expiry and near-expiry both page an action group."
  fi
fi

# ------------------------------- (6c) the gateway can actually read its own certificate
#
# APIM presents the client certificate that every other control here rests on, and it reads that
# certificate from Key Vault as its own managed identity. Without the role assignment there is no
# certificate on the backend connection, ingress rejects the handshake, and EVERY application
# request fails.
#
# Worth a guard rather than a comment because of where the failure lands: nothing in the APIM
# policy, the ingress manifests or either backend is wrong, so every other check in this script
# passes and the platform is still completely down. The missing piece is in a different file, in a
# different resource, in a different deployment step.
IDENTITIES="build/infra/identity/managed-identities.json"
if require_file "$IDENTITIES" "The managed identity and role assignment definitions"; then
  # The APIM identity block must exist and must carry a Key Vault role. Matched on the block rather
  # than on the file as a whole: a Key Vault role granted to a *deployable* elsewhere in the file
  # would otherwise satisfy a naive grep while the gateway still had none.
  apim_block="$(awk '/"name": "id-synthia-apim"/,/^    }/' "$IDENTITIES")"

  if [ -z "$apim_block" ]; then
    fail "No managed identity is defined for APIM, so it cannot read its own client certificate"
  elif ! printf '%s' "$apim_block" | grep -qF '"resource": "keyvault"'; then
    fail "The APIM identity holds no Key Vault role" \
      "APIM reads the gateway client certificate from Key Vault as this identity. Without it the
backend connection carries no certificate and every application request fails provenance."
  else
    pass "APIM has an identity that can read the gateway certificate from Key Vault."
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
