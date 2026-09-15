#!/usr/bin/env bash
#
# Local development commands.
#
# Every command here is a command CI runs. There is no gate you can only discover by pushing, and
# no gate here that CI does not also enforce — if the two drift, this file is the bug.

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
  build       Build all four trees
  test        Run every test suite
  lint        Lint and format-check every tree
  typecheck   Strict type checking (Python, web, desktop)
  boundaries  Cross-deployable boundary check, plus proof the guard fails correctly
  validate    Everything CI runs, in CI's order. Use this before pushing.
  clean       Remove build output

Single-tree shortcuts: dotnet | python | web | desktop
EOF
}

setup() {
  step "Restoring .NET";      (cd dotnet && dotnet restore Synthia.sln)
  step "Restoring Python";    (cd ragcore && uv sync --all-groups)
  step "Restoring web";       (cd apps/web && npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund)
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
}

check_web() {
  step "Angular"
  run "lint"        bash -c "cd apps/web && npx eslint ."
  run "format"      bash -c "cd apps/web && npx prettier --check ."
  run "build"       bash -c "cd apps/web && npm run build"
  run "test"        bash -c "cd apps/web && npm test"
}

check_desktop() {
  step "Electron"
  run "typecheck"       bash -c "cd apps/desktop && npx tsc -p tsconfig.json --noEmit"
  run "security suite"  bash -c "cd apps/desktop && npx vitest run"
}

check_boundaries() {
  step "Cross-deployable boundary"
  run "boundary check"  bash build/scripts/check-boundaries.sh
  run "guard verified"  bash build/scripts/verify-boundary-guard.sh
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
  lint)
    run "ruff check"  bash -c "cd ragcore && uv run ruff check ."
    run "ruff format" bash -c "cd ragcore && uv run ruff format --check ."
    run "dotnet format" bash -c "cd dotnet && dotnet format Synthia.sln --verify-no-changes"
    run "eslint"      bash -c "cd apps/web && npx eslint ."
    report ;;
  typecheck)
    run "mypy"           bash -c "cd ragcore && uv run mypy"
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
    run "web"     bash -c "cd apps/web && npm test"
    run "desktop" bash -c "cd apps/desktop && npx vitest run"
    report ;;
  validate)
    check_boundaries
    check_dotnet
    check_python
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
