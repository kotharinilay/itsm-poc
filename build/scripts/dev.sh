#!/usr/bin/env bash
#
# Local development commands.
#
# Every command here is a command CI runs. There is no gate you can only discover by pushing, and
# no gate here that CI does not also enforce — if the two drift, this file is the bug.
#
# `validate` runs every gate except the container images, which are `images` and need Docker running
# a build per deployable. Both together are the whole of CI. The list used to be shorter than CI
# while claiming otherwise: the desktop lint, build and guard prover, the web type check and
# accessibility sweep, the contract gates and the edge checks all ran only on the pipeline.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok()   { printf '  \xe2\x9c\x93 %s\n' "$1"; }
bad()  { printf '  \xe2\x9c\x97 %s\n' "$1"; }

failures=()
run() {
  local name="$1"
  shift
  if "$@"; then
    ok "$name"
  else
    bad "$name"
    failures+=("$name")
  fi
}

usage() {
  cat <<'EOF'
Usage: build/scripts/dev.sh <command>

  setup       Restore every toolchain (.NET, Python, web, desktop)
  build       Build the .NET, web and desktop trees
  test        Run every test suite
  lint        Lint and format-check every tree
  typecheck   Strict type checking (Python, web, desktop)
  boundaries  Boundary and edge checks, plus proof each guard fails correctly
  contracts   Emit the OpenAPI documents and check them against the committed ones
  validate    Everything CI runs, except the images. Use this before pushing.
  images      Build, start and inspect every container image (needs Docker)
  clean       Remove build output

Single-tree shortcuts: dotnet | python (RagCore + Integrations) | web | desktop
EOF
}

setup() {
  step "Restoring .NET";      (cd dotnet && dotnet restore Synthia.sln)
  step "Restoring Python";    (cd ragcore && uv sync --all-groups)
  step "Restoring Integrations"; (cd integrations && uv sync --all-groups)
  step "Restoring web";       (cd apps/web && npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund)
  # The accessibility sweep runs in `validate`, and Playwright's browser is not part of `npm ci`.
  step "Installing the sweep browser"; (cd apps/web && npx playwright install chromium)
  step "Restoring desktop";   (cd apps/desktop && npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund)
}

check_dotnet() {
  step ".NET"
  run "build (warnings as errors)" bash -c "cd dotnet && dotnet build Synthia.sln -warnaserror --nologo -v quiet"
  run "format"                     bash -c "cd dotnet && dotnet format Synthia.sln --verify-no-changes"
  run "test"                       bash -c "cd dotnet && dotnet test Synthia.sln --nologo -v quiet"
}

check_python() {
  step "Python / RagCore"
  run "ruff check"        bash -c "cd ragcore && uv run ruff check ."
  run "ruff format"       bash -c "cd ragcore && uv run ruff format --check ."
  run "mypy --strict"     bash -c "cd ragcore && uv run mypy"
  run "pytest"            bash -c "cd ragcore && uv run pytest -q"

  # A separate deployable with its own lock file (ADR-0007), so its gates run from its own tree.
  step "Python / Integrations"
  run "ruff check"        bash -c "cd integrations && uv run ruff check ."
  run "ruff format"       bash -c "cd integrations && uv run ruff format --check ."
  run "mypy --strict"     bash -c "cd integrations && uv run mypy"
  run "pytest"            bash -c "cd integrations && uv run pytest -q"
}

check_web() {
  step "Angular"
  run "lint"        bash -c "cd apps/web && npx eslint ."
  run "format"      bash -c "cd apps/web && npx prettier --check ."
  run "typecheck"   bash -c "cd apps/web && npx tsc -b --pretty"
  run "build"       bash -c "cd apps/web && npm run build"
  run "test"        bash -c "cd apps/web && npm test"
  # The axe-core sweep across all three surfaces (T049). It ran in neither CI nor this script: the
  # workflow step was conditional on a script that did not exist, so it printed a notice instead.
  run "accessibility sweep" bash -c "cd apps/web && npm run test:a11y"
}

check_desktop() {
  step "Electron"
  run "typecheck"       bash -c "cd apps/desktop && npm run typecheck"
  run "lint"            bash -c "cd apps/desktop && npm run lint"
  run "security suite"  bash -c "cd apps/desktop && npx vitest run"
  # The suite proves the controls hold; this proves the SUITE fails when one is weakened.
  run "security guard verified" bash build/scripts/verify-desktop-security-guard.sh
  run "build"           bash -c "cd apps/desktop && npm run build"
}

check_contracts() {
  step "API contracts"
  local emitted
  emitted="$(mktemp -d)"
  run "emit (RagCore)"      bash -c "cd ragcore && uv run python scripts/emit_contracts.py --out '$emitted/ragcore' >/dev/null"
  run "emit (Integrations)" bash -c "cd integrations && uv run python scripts/emit_contracts.py --out '$emitted/integrations' >/dev/null"
  # The committed document must be what the running service emits. The .NET documents are emitted by
  # its own contract tests during `dotnet test`, so a drift there shows up as a dirty tree.
  run "committed contracts current" bash -c "diff -r build/contracts/ragcore '$emitted/ragcore' && diff -r build/contracts/integrations '$emitted/integrations'"
  run "publishable"         bash -c "cd ragcore && uv run python ../build/scripts/openapi_validate.py --contracts ../build/contracts --policy ../build/policy/openapi-disclosure.json --version v1"
  run "contract guards verified" bash build/scripts/verify-contract-guards.sh
  rm -rf "$emitted"
}

check_boundaries() {
  step "Cross-deployable boundary"
  run "boundary check"  bash build/scripts/check-boundaries.sh
  run "boundary guard verified"     bash build/scripts/verify-boundary-guard.sh
  run "architecture guards verified" bash build/scripts/verify-architecture-guards.sh
  # The edge is committed configuration, and these are the checks that read it as configuration
  # rather than as prose (edge.yml).
  run "edge path"       bash build/scripts/check-edge-path.sh
  run "edge guard verified" bash build/scripts/verify-edge-guard.sh
}

report() {
  if [ "${#failures[@]}" -gt 0 ]; then
    printf '\n\033[1mFAILED\033[0m — %d gate(s):\n' "${#failures[@]}"
    printf '  - %s\n' "${failures[@]}"
    exit 1
  fi
  printf '\n\033[1mAll gates passed.\033[0m\n'
}

case "${1:-validate}" in
  setup)      setup ;;
  dotnet)     check_dotnet; report ;;
  python)     check_python; report ;;
  web)        check_web; report ;;
  desktop)    check_desktop; report ;;
  boundaries) check_boundaries; report ;;
  images)     step "Container images"; run "build, start, inspect" bash build/scripts/smoke-images.sh; report ;;
  lint)
    run "ruff check"  bash -c "cd ragcore && uv run ruff check ."
    run "ruff format" bash -c "cd ragcore && uv run ruff format --check ."
    run "ruff check (integrations)"  bash -c "cd integrations && uv run ruff check ."
    run "ruff format (integrations)" bash -c "cd integrations && uv run ruff format --check ."
    run "dotnet format" bash -c "cd dotnet && dotnet format Synthia.sln --verify-no-changes"
    run "eslint"      bash -c "cd apps/web && npx eslint ."
    report ;;
  typecheck)
    run "mypy"           bash -c "cd ragcore && uv run mypy"
    run "mypy (integrations)" bash -c "cd integrations && uv run mypy"
    run "tsc (desktop)"  bash -c "cd apps/desktop && npx tsc -p tsconfig.json --noEmit"
    report ;;
  build)
    run ".NET"    bash -c "cd dotnet && dotnet build Synthia.sln -warnaserror --nologo -v quiet"
    run "web"     bash -c "cd apps/web && npm run build"
    run "desktop" bash -c "cd apps/desktop && npm run build"
    report ;;
  test)
    run ".NET"    bash -c "cd dotnet && dotnet test Synthia.sln --nologo -v quiet"
    run "python"  bash -c "cd ragcore && uv run pytest -q"
    run "integrations" bash -c "cd integrations && uv run pytest -q"
    run "web"     bash -c "cd apps/web && npm test"
    run "desktop" bash -c "cd apps/desktop && npx vitest run"
    report ;;
  contracts)  check_contracts; report ;;
  validate)
    check_boundaries
    check_dotnet
    check_python
    check_contracts
    check_web
    check_desktop
    report ;;
  clean)
    rm -rf dotnet/**/bin dotnet/**/obj apps/web/dist apps/web/.angular apps/desktop/dist
    find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
    ok "cleaned" ;;
  -h|--help|help) usage ;;
  *) usage; exit 1 ;;
esac
