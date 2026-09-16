#!/usr/bin/env bash
#
# T055 gate — prove the Electron security suite actually fails.
#
# Plan Stage 4's validation gate is not "the security suite passes". It is "the security suite
# passes, AND fails correctly when a setting is flipped". A suite that would stay green with
# `sandbox: false` is not evidence of anything, and nobody finds out until it matters.
#
# So this script flips each control in turn — in a scratch copy of apps/desktop, never in the
# working tree — asserts the suite goes red, and finally asserts the unmodified copy is green.
#
# Exit 0 = every planted violation was caught, and the clean tree passed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP="$ROOT/apps/desktop"

if [ ! -d "$DESKTOP/node_modules" ]; then
  echo "apps/desktop dependencies are not installed. Run: cd apps/desktop && npm ci" >&2
  exit 1
fi

SCRATCH="$(mktemp -d)"
cleanup() { rm -rf "$SCRATCH"; }
trap cleanup EXIT

# A copy, so a planted violation can never be committed by accident. node_modules is symlinked
# rather than copied: it is large, and nothing here modifies it.
mkdir -p "$SCRATCH/desktop"
for entry in src tests package.json tsconfig.json vitest.config.ts; do
  cp -R "$DESKTOP/$entry" "$SCRATCH/desktop/$entry"
done
ln -s "$DESKTOP/node_modules" "$SCRATCH/desktop/node_modules"

# The renderer-contract suite reads apps/web by relative path, which does not exist beside the
# scratch copy. Its subject is drift between two files, not a security switch, so it is not part
# of this gate and is removed from the copy.
rm -f "$SCRATCH/desktop/tests/renderer-contract.spec.ts"

failures=0

run_suite() {
  (cd "$SCRATCH/desktop" && node node_modules/vitest/vitest.mjs run) >/dev/null 2>&1
}

restore() {
  cp -R "$DESKTOP/src/." "$SCRATCH/desktop/src/"
}

# Plant one violation with sed, run the suite, assert it fails, then restore.
expect_caught() {
  local description="$1" file="$2" pattern="$3" replacement="$4"

  local target="$SCRATCH/desktop/$file"
  if ! grep -qE "$pattern" "$target"; then
    printf '  \xe2\x9c\x97 CANNOT PLANT: %s (pattern not found in %s)\n' "$description" "$file"
    failures=$((failures + 1))
    return
  fi

  sed -i -E "s|$pattern|$replacement|" "$target"

  if run_suite; then
    printf '  \xe2\x9c\x97 NOT CAUGHT: %s\n' "$description"
    failures=$((failures + 1))
  else
    printf '  \xe2\x9c\x93 caught: %s\n' "$description"
  fi

  restore
}

echo "Verifying the Electron security suite fails when a control is weakened..."

# ---------------------------------------------------------------- webPreferences switches
expect_caught "sandbox disabled" \
  "src/main/window.ts" '  sandbox: true,' '  sandbox: false,'

expect_caught "contextIsolation disabled" \
  "src/main/window.ts" '  contextIsolation: true,' '  contextIsolation: false,'

expect_caught "nodeIntegration enabled" \
  "src/main/window.ts" '  nodeIntegration: false,' '  nodeIntegration: true,'

expect_caught "webSecurity disabled" \
  "src/main/window.ts" '  webSecurity: true,' '  webSecurity: false,'

expect_caught "insecure content allowed" \
  "src/main/window.ts" '  allowRunningInsecureContent: false,' '  allowRunningInsecureContent: true,'

expect_caught "webview tag enabled" \
  "src/main/window.ts" '  webviewTag: false,' '  webviewTag: true,'

# ---------------------------------------------------------------- navigation allow-list
expect_caught "plain HTTP added to the navigable schemes" \
  "src/main/config.ts" \
  "export const ALLOWED_REMOTE_SCHEMES: readonly string\[\] = \['https:', 'wss:'\];" \
  "export const ALLOWED_REMOTE_SCHEMES: readonly string[] = ['https:', 'wss:', 'http:'];"

expect_caught "the external-open scheme loosened to file" \
  "src/main/config.ts" \
  "export const EXTERNAL_SCHEME = 'https:';" \
  "export const EXTERNAL_SCHEME = 'file:';"

# ---------------------------------------------------------------- CSP
expect_caught "'unsafe-eval' added to script-src" \
  "src/main/csp.ts" \
  "  \"script-src 'self'\"," \
  "  \"script-src 'self' 'unsafe-eval'\","

expect_caught "'unsafe-inline' added to style-src" \
  "src/main/csp.ts" \
  "  const styleSrc = nonce === null \? \"style-src 'self'\" : " \
  "  const styleSrc = nonce === null ? \"style-src 'self' 'unsafe-inline'\" : "

expect_caught "frame-ancestors loosened" \
  "src/main/csp.ts" \
  "  \"frame-ancestors 'none'\"," \
  "  \"frame-ancestors \\*\","

# ---------------------------------------------------------------- IPC validation
expect_caught "sender validation removed" \
  "src/main/ipc-guard.ts" \
  '  return trustedOrigins.includes\(origin\);' \
  '  return true;'

expect_caught "argument validation removed" \
  "src/ipc-contracts/index.ts" \
  '  return validator === undefined \? false : validator\(args\);' \
  '  return true;'

# ---------------------------------------------------------------- process hardening
expect_caught "a certificate error trusted" \
  "src/main/app-shell.ts" \
  'export const TRUST_CERTIFICATE_ERRORS = false;' \
  'export const TRUST_CERTIFICATE_ERRORS = true;'

expect_caught "the endpoint execution boundary made to succeed" \
  "src/main/endpoint-execution-boundary.ts" \
  'export const IS_IMPLEMENTED = false;' \
  'export const IS_IMPLEMENTED = true;'

# ---------------------------------------------------------------- bundle containment
expect_caught "path containment removed from the renderer protocol" \
  "src/main/renderer-protocol.ts" \
  '    candidate === root \|\| candidate.startsWith\(root \+ path.sep\);' \
  '    true;'

# ---------------------------------------------------------------- the clean tree must pass
echo "Verifying the unmodified suite passes..."
if run_suite; then
  printf '  \xe2\x9c\x93 clean tree passes\n'
else
  printf '  \xe2\x9c\x97 the unmodified suite does NOT pass\n'
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  printf '\nDesktop security guard verification FAILED with %d problem(s).\n' "$failures"
  echo "A control that stays green when it is weakened is not a control. Either the assertion is"
  echo "missing from apps/desktop/tests/, or this script's planted pattern no longer matches the"
  echo "source - fix whichever it is, rather than removing the case."
  exit 1
fi

printf '\n  \xe2\x9c\x93 Every weakened control was caught, and the clean suite passes.\n'
exit 0
