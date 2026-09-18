#!/usr/bin/env bash
#
# Prove the OpenAPI contract guards actually fail.
#
# A GUARD NOBODY HAS SEEN FAIL IS A GUARD NOBODY KNOWS WORKS. openapi_validate.py and
# openapi_diff.py both walk a generated document looking for a shape. A walk that stops finding
# anything - because a key was renamed by a generator upgrade, because a document grew a level of
# nesting, or because a policy entry was quietly deleted - reports success exactly as loudly as a
# walk that found nothing wrong. The failure mode of a contract gate is silence.
#
# So this plants each violation class into a throwaway copy of a real emitted document, asserts the
# guard rejects it, and finally asserts the real documents pass. Nothing under build/contracts/ is
# modified: every edit happens in a temporary directory, which is also why this is safe to run
# locally.
#
# Exit 0 = every planted violation was caught and the committed contracts passed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# python3 where it exists, python otherwise — Linux CI has the first, a Windows developer shell
# usually only has the second, and this script is meant to run in both.
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"
VALIDATE="build/scripts/openapi_validate.py"
DIFF="build/scripts/openapi_diff.py"
POLICY="build/policy/openapi-disclosure.json"
APPROVALS="build/contracts/approved-breaking-changes.json"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

failures=0

pass() { printf '  \xe2\x9c\x93 caught: %s\n' "$1"; }
fail() { printf '  \xe2\x9c\x97 NOT CAUGHT: %s\n' "$1"; failures=$((failures + 1)); }

# Build a one-document tree under $WORK/<case>/<audience>.v1.openapi.json, with a Python edit
# applied. The audience is part of the FILE NAME because the validator reads it from there - the
# tenantId narrowing is permitted on staff and on nothing else, and a fixture that lost the name
# would test the wrong rule.
plant() {
  local case_name="$1" source="$2" audience="$3" edit="$4"
  local target="$WORK/$case_name"

  mkdir -p "$target"
  cp "$source" "$target/$audience.v1.openapi.json"

  "$PYTHON" - "$target/$audience.v1.openapi.json" <<PYTHON
import json, sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    document = json.load(handle)

$edit

with open(path, "w", encoding="utf-8") as handle:
    json.dump(document, handle, indent=2, sort_keys=True)
PYTHON

  echo "$target"
}

expect_validator_rejects() {
  local description="$1" tree="$2"
  if "$PYTHON" "$VALIDATE" --contracts "$tree" --policy "$POLICY" >/dev/null 2>&1; then
    fail "$description"
  else
    pass "$description"
  fi
}

expect_comparator_rejects() {
  local description="$1" tree="$2"
  if "$PYTHON" "$DIFF" --baseline build/contracts/ragcore --current "$tree" \
      --approved "$APPROVALS" >/dev/null 2>&1; then
    fail "$description"
  else
    pass "$description"
  fi
}

CUSTOMER="build/contracts/ragcore/customer.v1.openapi.json"
STAFF="build/contracts/dotnet/staff.v1.openapi.json"
INTEGRATIONS="build/contracts/integrations/workload.v1.openapi.json"

echo "Planting violations the validator must reject:"

# A credential-shaped name anywhere in the document. The rule matches NAMES, so this plants a
# field rather than a description - a description saying an operation carries no credential is
# correct documentation, and a scanner that flagged it would get the documentation deleted.
expect_validator_rejects "a secret-bearing field name" "$(plant secret "$CUSTOMER" customer '
document["components"]["schemas"]["ConsentRequest"]["properties"]["apiKey"] = {"type": "string"}
')"

# Internal implementation detail. A client that can see it starts depending on it, and then the
# detail is a contract nobody agreed to.
expect_validator_rejects "an internal-only name" "$(plant internal "$CUSTOMER" customer '
document["components"]["schemas"]["ConsentRequest"]["properties"]["checkpoint"] = {"type": "string"}
')"

# THE AUTHORITY CHANNEL, in its two shapes. A query parameter on an audience where the narrowing
# exception does not apply, and a request-body field anywhere.
expect_validator_rejects "a tenant query parameter on the customer audience" \
  "$(plant authority_query "$CUSTOMER" customer '
for item in document["paths"].values():
    for operation in item.values():
        operation.setdefault("parameters", []).append(
            {"name": "tenantId", "in": "query", "schema": {"type": "string"}}
        )
        break
    break
')"

expect_validator_rejects "a tenant field in a request body" \
  "$(plant authority_body "$CUSTOMER" customer '
document["components"]["schemas"]["ConsentRequest"]["properties"]["tenantId"] = {"type": "string"}
')"

expect_validator_rejects "a roles field in a request body" \
  "$(plant authority_roles "$CUSTOMER" customer '
document["components"]["schemas"]["ConsentRequest"]["properties"]["roles"] = {"type": "array"}
')"

# THE SAME RULE, ON THE INTEGRATIONS DOCUMENT. Planted against a THIRD deployable's artifact
# deliberately: every case above uses RagCore's or the monolith's, so none of them exercises this
# document's shape - a workload-audience document whose schemas are named differently.
#
# To be precise about what this does and does not prove: it plants into a throwaway copy, so it
# shows the RULE applies to this document, not that CI walks build/contracts/integrations. What
# catches the tree being dropped from the walk is the "every committed document is publishable"
# assertion at the end of this script, plus the staleness diff in contracts.yml.
#
# The rule is also load-bearing here in a way it is not elsewhere. This surface is the synchronous
# seam RagCore calls, and `FR-INTEG-018` says the organisation is recovered from the durable object
# an opaque identifier names — NEVER from the request. A `tenantId` accepted on this body would let
# the caller choose whose data is touched, which is the one thing the whole boundary exists to stop.
expect_validator_rejects "a tenant field on the Integrations request body" \
  "$(plant integrations_authority "$INTEGRATIONS" workload '
document["components"]["schemas"]["CaseOperationRequest"]["properties"]["tenantId"] = {
    "type": "string"
}
')"

# RFC 9457. Two ways to get it wrong: publish the error at the wrong media type, or publish no
# error at all. The second is the one that looks fine in a diff.
expect_validator_rejects "an error response that is not problem+json" \
  "$(plant problem_media "$CUSTOMER" customer '
for item in document["paths"].values():
    for operation in item.values():
        for code, response in operation.get("responses", {}).items():
            if not code.startswith("2") and "content" in response:
                response["content"] = {"application/json": {"schema": {"type": "string"}}}
')"

expect_validator_rejects "an operation declaring no error response at all" \
  "$(plant problem_missing "$CUSTOMER" customer '
for item in document["paths"].values():
    for operation in item.values():
        operation["responses"] = {
            code: response
            for code, response in operation.get("responses", {}).items()
            if code.startswith("2")
        }
        operation["responses"].setdefault("200", {"description": "OK"})
')"

# Configuration material. A servers block names the host the document was generated on, which
# differs between the machine that emits and the machine that verifies.
expect_validator_rejects "a published servers block" "$(plant servers "$CUSTOMER" customer '
document["servers"] = [{"url": "https://internal.example.invalid/"}]
')"

# Versioned by the API version, not by an assembly version that moves on a patch release changing
# no route.
expect_validator_rejects "a document versioned by something other than its API version" \
  "$(plant version "$CUSTOMER" customer '
document["info"]["version"] = "1.0.0"
')"

echo
echo "Planting differences the comparator must reject:"

expect_comparator_rejects "an operation removed" "$(plant removed "$CUSTOMER" customer '
document["paths"].pop(sorted(document["paths"])[0])
')"

expect_comparator_rejects "an optional request field made required" \
  "$(plant required "$CUSTOMER" customer '
schema = document["components"]["schemas"]["FeedbackRequest"]
schema["properties"]["note"] = {"type": "string"}
schema["required"] = sorted(set(schema.get("required", [])) | {"note"})
')"

echo
echo "The approval register, in both directions:"

# THE ESCAPE HATCH HAS TO WORK, AND HAS TO BE NARROW. A register that never lets anything through
# is one somebody deletes the day they need it; a register that matches loosely approves the change
# nobody looked at. So: the same removal is asserted to fail unapproved, to pass with an approval
# quoting it verbatim, to fail again when the approval has expired, and to fail again when the
# approval is for a different finding.
REMOVED_TREE="$(plant approval_case "$CUSTOMER" customer '
document["paths"].pop(sorted(document["paths"])[0])
')"

# EVERY finding, not the first. Removing one path removes each of its operations, so approving one
# of them leaves the change unapproved - which is the register working, and would look here like the
# register failing.
mapfile -t REMOVED_FINDINGS < <(
  "$PYTHON" "$DIFF" --baseline build/contracts/ragcore --current "$REMOVED_TREE" 2>/dev/null \
    | sed -n 's/^::error::[^:]*\.json: BREAKING //p'
)

write_register() {
  local path="$1" expires="$2"
  shift 2
  "$PYTHON" - "$path" "$expires" "$@" <<'PYTHON'
import json, sys

path, expires, findings = sys.argv[1], sys.argv[2], sys.argv[3:]
register = {
    "approvals": [
        {
            "document": "customer.v1.openapi.json",
            "finding": finding,
            "approvedBy": "verify-contract-guards.sh",
            "approvedOn": "2026-09-17",
            "expiresOn": expires,
            "reason": "Fixture. Proves the register is honoured and that it is honoured narrowly.",
            "clientMigration": "none - fixture",
        }
        for finding in findings
    ]
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(register, handle, indent=2)
PYTHON
}

expect_diff() {
  local description="$1" register="$2" expected="$3"
  "$PYTHON" "$DIFF" --baseline build/contracts/ragcore --current "$REMOVED_TREE" \
    --approved "$register" --today 2026-09-17 >/dev/null 2>&1
  local actual=$?
  if [ "$actual" -eq "$expected" ]; then
    pass "$description"
  else
    fail "$description (expected exit $expected, got $actual)"
  fi
}

if [ "${#REMOVED_FINDINGS[@]}" -eq 0 ]; then
  fail "the comparator reported no finding to approve"
else
  expect_diff "an unapproved removal still fails" "$APPROVALS" 1

  write_register "$WORK/current.json" "2099-01-01" "${REMOVED_FINDINGS[@]}"
  expect_diff "an approved removal is allowed through" "$WORK/current.json" 0

  write_register "$WORK/expired.json" "2026-09-16" "${REMOVED_FINDINGS[@]}"
  expect_diff "an EXPIRED approval does not apply" "$WORK/expired.json" 1

  write_register "$WORK/other.json" "2099-01-01" \
    "operation removed: GET /api/customer/v1/something-else"
  expect_diff "an approval for a different finding does not apply" "$WORK/other.json" 1
fi

echo
echo "The committed contracts themselves:"

if "$PYTHON" "$VALIDATE" --contracts build/contracts --policy "$POLICY" >/dev/null 2>&1; then
  printf '  \xe2\x9c\x93 every committed document is publishable\n'
else
  printf '  \xe2\x9c\x97 a committed document is NOT publishable\n'
  "$PYTHON" "$VALIDATE" --contracts build/contracts --policy "$POLICY"
  failures=$((failures + 1))
fi

# The other half of a guard's correctness, and the half that never gets written: a guard that
# rejects everything catches every planted violation and is useless. The staff document carries
# tenantId as a query parameter legitimately, so this is also the assertion that the narrowing
# exception is honoured rather than merely written down.
if "$PYTHON" "$VALIDATE" --contracts "$(dirname "$STAFF")" --policy "$POLICY" >/dev/null 2>&1; then
  printf '  \xe2\x9c\x93 the staff tenantId narrowing is accepted, not rejected\n'
else
  printf '  \xe2\x9c\x97 the staff tenantId narrowing was rejected; the guard is too broad\n'
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "All contract guards behave as declared."
  exit 0
fi

echo "$failures contract guard(s) did not behave as declared."
exit 1
