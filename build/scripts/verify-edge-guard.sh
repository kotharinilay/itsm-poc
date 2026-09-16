#!/usr/bin/env bash
#
# Prove the edge path guard actually fails.
#
# A GUARD NOBODY HAS SEEN FAIL IS A GUARD NOBODY KNOWS WORKS. This plants each violation class in
# turn, asserts check-edge-path.sh rejects it, restores the file, and finally asserts a clean tree
# passes. It runs in CI, so a change that quietly weakens the guard is caught by the thing that
# proves it.
#
# This matters more for the edge guard than for most. Every check in check-edge-path.sh is a
# grep against a file that is rarely edited, and a grep that stops matching - because a header was
# renamed, a file moved, or a pattern was tightened - reports success just as loudly as a grep that
# matches. The failure mode of this guard is silence.
#
# Exit 0 = the guard rejected every planted violation and accepted the clean tree.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GUARD="build/scripts/check-edge-path.sh"
failures=0
backups=()

# Save a file so the planted edit can be undone whatever happens next - including a failed
# assertion, a syntax error in this script, or the runner cancelling the job. A guard verifier that
# can leave the tree modified is one that turns a red build into a corrupted working copy.
save() {
  local path="$1"
  local backup
  backup="$(mktemp)"
  cp "$path" "$backup"
  backups+=("$path:$backup")
}

restore() {
  local entry path backup
  for entry in "${backups[@]:-}"; do
    [ -n "$entry" ] || continue
    path="${entry%%:*}"
    backup="${entry#*:}"
    [ -f "$backup" ] && cp "$backup" "$path" && rm -f "$backup"
  done
  backups=()
}

trap restore EXIT

expect_rejected() {
  local description="$1"
  if bash "$GUARD" >/dev/null 2>&1; then
    printf '  \xe2\x9c\x97 NOT CAUGHT: %s\n' "$description"
    failures=$((failures + 1))
  else
    printf '  \xe2\x9c\x93 caught: %s\n' "$description"
  fi
}

# The other half of a guard's correctness, and the half that never gets written: a guard is only
# useful if it also stays QUIET on things that are fine. One that cries wolf on correct code is one
# somebody adds a skip for, and a skipped guard protects nothing.
expect_accepted() {
  local description="$1"
  if bash "$GUARD" >/dev/null 2>&1; then
    printf '  \xe2\x9c\x93 accepted: %s\n' "$description"
  else
    printf '  \xe2\x9c\x97 FALSE POSITIVE: %s\n' "$description"
    bash "$GUARD" 2>&1 | sed 's/^/        /'
    failures=$((failures + 1))
  fi
}

echo "Verifying the edge path guard rejects each violation class..."

# 1 - a backend published to the internet.
#
# The one that matters most: it is a single word, it reviews as a formatting change, and it puts a
# public route straight onto a backend that trusts whatever identity headers it is handed.
MANIFEST="build/docker/containerapps/monolith.yaml"
save "$MANIFEST"
sed -i 's/^\([[:space:]]*\)external: false/\1external: true/' "$MANIFEST"
expect_rejected "a container app publishing external ingress"
restore

# 2 - a backend that no longer demands the gateway certificate.
#
# Downgraded to `accept` rather than deleted, because `accept` is the plausible mistake: it reads
# like a softer form of the same thing and is in fact no control at all.
save "$MANIFEST"
sed -i 's/^\([[:space:]]*\)clientCertificateMode: require/\1clientCertificateMode: accept/' "$MANIFEST"
expect_rejected "a container app downgrading the client certificate to 'accept'"
restore

# 3 - the gateway no longer strips an inbound copy of the contract.
#
# Only the roles header is removed. A caller supplying X-Idp-Roles alone would then reach a backend
# with a role set of its own choosing, while the other four headers still look correctly handled -
# which is why the guard checks every header rather than sampling one.
GLOBAL_POLICY="build/infra/apim/global.inbound.xml"
save "$GLOBAL_POLICY"
grep -v '<set-header name="X-Idp-Roles" exists-action="delete" />' "$GLOBAL_POLICY" > "$GLOBAL_POLICY.tmp"
mv "$GLOBAL_POLICY.tmp" "$GLOBAL_POLICY"
expect_rejected "the gateway not stripping an inbound X-Idp-Roles"
restore

# 4 - the gateway no longer strips the forwarded certificate header.
#
# The most dangerous single deletion in the tree: a caller who can set X-Forwarded-Client-Cert is
# asserting gateway provenance itself, which every other control here rests on.
save "$GLOBAL_POLICY"
grep -v '<set-header name="X-Forwarded-Client-Cert" exists-action="delete" />' "$GLOBAL_POLICY" > "$GLOBAL_POLICY.tmp"
mv "$GLOBAL_POLICY.tmp" "$GLOBAL_POLICY"
expect_rejected "the gateway not stripping an inbound X-Forwarded-Client-Cert"
restore

# 5 - the origin stops being specific to this platform.
#
# Removing the FDID check leaves the service tag as the only control, and that tag admits every
# Azure customer's Front Door.
save "$GLOBAL_POLICY"
sed -i 's/{{front-door-id}}/anything/' "$GLOBAL_POLICY"
expect_rejected "the gateway not checking this platform's Front Door identifier"
restore

# 5b - the client certificate referenced by thumbprint.
#
# The spelling that looks MORE precise and is in fact the broken one: a Key Vault certificate's
# thumbprint changes on rotation, and the policy then silently stops attaching a certificate at
# all. Planted because this is a mistake that works perfectly right up until the day it doesn't,
# and because it was the actual defect in the first version of this policy.
save "$GLOBAL_POLICY"
sed -i 's/certificate-id="{{gateway-client-certificate-id}}"/thumbprint="{{gateway-client-certificate-thumbprint}}"/' "$GLOBAL_POLICY"
expect_rejected "the client certificate referenced by thumbprint rather than certificate-id"
restore

# 6 - an audience that derives no identity.
AUDIENCE_POLICY="build/infra/apim/staff.v1.xml"
save "$AUDIENCE_POLICY"
sed -i 's/<validate-azure-ad-token/<disabled-validate-azure-ad-token/' "$AUDIENCE_POLICY"
expect_rejected "an audience policy that validates no token"
restore

# 7 - a second Front Door origin.
#
# A public route to a backend that looks, in the portal, like a routing entry.
FRONTDOOR="build/infra/frontdoor/front-door.json"
save "$FRONTDOOR"
sed -i 's/"hostName": "${APIM_GATEWAY_HOSTNAME}",/"hostName": "${APIM_GATEWAY_HOSTNAME}",\n          "hostName": "${BACKEND_DIRECT_HOSTNAME}",/' "$FRONTDOOR"
expect_rejected "a second Front Door origin host"
restore

# 8 - a service calling another by its internal address.
#
# Planted in production source, because that is where it would appear - and because the guard must
# distinguish this from the several files that describe the rule in prose.
PLANTED="ragcore/src/ragcore/__planted_edge_violation.py"
cat > "$PLANTED" <<'EOF'
# Planted by verify-edge-guard.sh. Removed automatically.
MONOLITH = "http://synthia-monolith.internal.azurecontainerapps.io/api/staff/v1/sessions"
EOF
expect_rejected "a service addressing another by its internal address"
rm -f "$PLANTED"

# 9 - the shared registry itself removed.
#
# Every rule above is a restatement of something that file declares. Its absence must fail loudly,
# not leave the platform unguarded while every other check still reports success.
POLICY="build/policy/edge-trust.json"
save "$POLICY"
rm -f "$POLICY"
expect_rejected "the shared edge trust policy being deleted"
restore

# 9b - expiry alerting that notifies nobody.
#
# The plausible regression, and the one a review waves through: the event subscriptions are still
# there, still filtered correctly, still named after the right certificate - and the destination
# has lost its action group, so the whole thing is a dashboard nobody looks at. The alert appears
# to exist right up until the morning it needed to wake somebody.
EXPIRY_ALERTS="build/infra/monitoring/gateway-certificate-expiry.json"
save "$EXPIRY_ALERTS"
sed -i 's/"actionGroups"/"disabledActionGroups"/g' "$EXPIRY_ALERTS"
expect_rejected "certificate expiry alerts that reach no action group"
restore

# 9c - the near-expiry alert removed entirely, leaving only the expired alert.
#
# Also plausible, because the 30-day alert is the noisy one and the expired alert feels like the
# important one. It is exactly backwards: by the time CertificateExpired fires the platform is
# already down, and the near-expiry alert was the only chance to prevent that.
save "$EXPIRY_ALERTS"
sed -i 's/Microsoft.KeyVault.CertificateNearExpiry/Microsoft.KeyVault.CertificateSomethingElse/' "$EXPIRY_ALERTS"
expect_rejected "the certificate near-expiry alert being removed"
restore

# 9d - the gateway loses its Key Vault access.
#
# The subtlest failure this suite covers. Nothing in the APIM policy, the ingress manifests or
# either backend changes - every other check still passes - and the platform is completely down,
# because APIM cannot read the certificate it is configured to present.
#
# The role is removed from the APIM identity only, leaving the deployables' Key Vault roles intact,
# which is what a naive file-wide grep would have been fooled by.
IDENTITIES="build/infra/identity/managed-identities.json"
save "$IDENTITIES"
sed -i '/"name": "id-synthia-apim"/,/^    }/ s/"resource": "keyvault"/"resource": "none"/' "$IDENTITIES"
expect_rejected "the APIM identity losing its Key Vault role"
restore

# 10 - A WORKER MANIFEST MUST NOT BE REJECTED.
#
# Workers consume Service Bus by dialling OUT over AMQP as a managed identity. They declare no
# ingress, accept no inbound request, and there is no connection for a client certificate to appear
# on - so demanding clientCertificateMode of them is meaningless.
#
# This is the case that motivated the fix. The guard originally required the setting on EVERY
# manifest, which would have failed the first correctly-written worker somebody added, on their
# first attempt, for something that is not a defect. That is how guards get skipped.
WORKER="build/docker/containerapps/__planted_worker.yaml"
cat > "$WORKER" <<'EOF'
# Planted by verify-edge-guard.sh. Removed automatically.
# A Service Bus consumer: no ingress, no inbound request, no client certificate to present.
apiVersion: 2024-03-01
type: Microsoft.App/containerApps
name: synthia-resume-worker
properties:
  configuration:
    activeRevisionsMode: Single
  template:
    containers:
      - name: synthia-resume-worker
        image: registry.example/synthia-ragcore@sha256:planted
EOF
expect_accepted "a worker manifest that declares no ingress"
rm -f "$WORKER"

# ---------------------------------------------------------------- the clean tree
#
# Asserted last and explicitly. Without it, a guard that had been broken into rejecting EVERYTHING
# would pass all nine checks above - the verifier would be confirming its own uselessness.
echo ""
if bash "$GUARD" >/dev/null 2>&1; then
  printf '  \xe2\x9c\x93 a clean tree passes\n'
else
  printf '  \xe2\x9c\x97 A CLEAN TREE FAILS - the guard rejects the repository as committed.\n'
  bash "$GUARD" 2>&1 | sed 's/^/      /'
  failures=$((failures + 1))
fi

echo ""
if [ "$failures" -gt 0 ]; then
  printf 'Edge guard verification FAILED: %d case(s) the guard does not catch.\n' "$failures"
  echo "The guard is what stands between a one-line configuration change and a backend that anybody"
  echo "can hand forged identity headers. A guard that has stopped catching something is worse than"
  echo "no guard, because the build still goes green."
  exit 1
fi

printf 'The edge path guard catches every violation class, and accepts a clean tree.\n'
exit 0
