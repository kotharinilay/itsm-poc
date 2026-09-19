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

# 5 - the origin stops being specific to this platform.
#
# Removing the FDID check leaves the service tag as the only control, and that tag admits every
# Azure customer's Front Door.
save "$GLOBAL_POLICY"
sed -i 's/{{front-door-id}}/anything/' "$GLOBAL_POLICY"
expect_rejected "the gateway not checking this platform's Front Door identifier"
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

# 10 - A WORKER MANIFEST MUST NOT BE REJECTED.
#
# Workers consume Service Bus by dialling OUT over AMQP as a managed identity. They declare no
# ingress and accept no inbound request, so the ingress rules have nothing to say about them.
#
# Retained after the gateway-certificate checks were removed (ADR 0008), because the lesson it
# encodes outlives them: a guard that fails the first correctly-written worker somebody adds, for
# something that is not a defect, is a guard that gets skipped.
WORKER="build/docker/containerapps/__planted_worker.yaml"
cat > "$WORKER" <<'EOF'
# Planted by verify-edge-guard.sh. Removed automatically.
# A Service Bus consumer: no ingress and no inbound request.
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
