#!/usr/bin/env bash
#
# T022 — prove the boundary guard actually fails.
#
# A guard nobody has seen fail is a guard nobody knows works. This plants each violation class in
# turn, asserts check-boundaries.sh rejects it, removes it, and finally asserts a clean tree passes.
# It runs in CI, so a change that quietly weakens the guard is caught by the thing that proves it.
#
# Exit 0 = the guard rejected every planted violation and accepted the clean tree.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GUARD="build/scripts/check-boundaries.sh"
failures=0
planted=()

cleanup() {
  for path in "${planted[@]:-}"; do
    [ -n "$path" ] && rm -rf "$path"
  done
}
trap cleanup EXIT

expect_rejected() {
  local description="$1"
  if bash "$GUARD" >/dev/null 2>&1; then
    printf '  \xe2\x9c\x97 NOT CAUGHT: %s\n' "$description"
    failures=$((failures + 1))
  else
    printf '  \xe2\x9c\x93 caught: %s\n' "$description"
  fi
}

echo "Verifying the boundary guard rejects each violation class..."

# 1 — .NET source naming RagCore
mkdir -p dotnet/src/Synthia.Api
cat > dotnet/src/Synthia.Api/__PlantedViolation.cs <<'EOF'
// Planted by verify-boundary-guard.sh. Removed automatically.
internal static class PlantedViolation
{
    public const string Target = "http://ragcore:8000/api";
}
EOF
planted+=("dotnet/src/Synthia.Api/__PlantedViolation.cs")
expect_rejected ".NET source referencing RagCore"
rm -f dotnet/src/Synthia.Api/__PlantedViolation.cs

# 2 — RagCore importing a .NET module
mkdir -p ragcore/src/ragcore
cat > ragcore/src/ragcore/__planted_violation.py <<'EOF'
# Planted by verify-boundary-guard.sh. Removed automatically.
from Synthia.Contracts import Something
EOF
planted+=("ragcore/src/ragcore/__planted_violation.py")
expect_rejected "RagCore importing a .NET module"
rm -f ragcore/src/ragcore/__planted_violation.py

# 3 — an EF Migrations directory in the monolith
mkdir -p dotnet/src/Synthia.Persistence/Migrations
touch dotnet/src/Synthia.Persistence/Migrations/.keep
planted+=("dotnet/src/Synthia.Persistence/Migrations")
expect_rejected "EF Migrations directory in the monolith"
rm -rf dotnet/src/Synthia.Persistence/Migrations

# 4 — a schema-owning EF call
cat > dotnet/src/Synthia.Persistence/__PlantedMigrate.cs <<'EOF'
// Planted by verify-boundary-guard.sh. Removed automatically.
internal static class PlantedMigrate
{
    public static void Run(dynamic db) => db.Database.Migrate();
}
EOF
planted+=("dotnet/src/Synthia.Persistence/__PlantedMigrate.cs")
expect_rejected "Database.Migrate() call in the monolith"
rm -f dotnet/src/Synthia.Persistence/__PlantedMigrate.cs

# 5 — a clean tree must pass
if bash "$GUARD" >/dev/null 2>&1; then
  printf '  \xe2\x9c\x93 clean tree accepted\n'
else
  printf '  \xe2\x9c\x97 clean tree REJECTED - the guard has a false positive\n'
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  printf '\nGuard verification FAILED: %d case(s) wrong.\n' "$failures"
  exit 1
fi

printf '\nGuard verified: every violation class is rejected, a clean tree passes.\n'
exit 0
