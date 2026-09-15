#!/usr/bin/env bash
#
# Cross-deployable boundary check (T013, ADR-0001, constitution Principle V).
#
# RagCore and the .NET monolith have NO application-level dependency in either direction — no API
# call, no library reference, no deployment coupling. They meet at exactly two places: PostgreSQL,
# through versioned views RagCore owns, and Service Bus, through opaque triggers.
#
# No compiler catches this, because there is nothing to compile across the boundary. This script is
# what catches it, and it runs as a required CI check.
#
# Implementation note: plain `find` + `grep` only. An earlier version switched between ripgrep and
# grep depending on what was installed, and the two disagreed — it passed a planted violation.
# A guard that can silently stop guarding is worse than no guard, so this one has a single path.
#
# Exit 0 = boundary intact. Exit 1 = violation(s), with the offending lines printed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

violations=0

# Collect source files under a tree, skipping build output and dependency directories.
sources() {
  local tree="$1"
  shift
  [ -d "$tree" ] || return 0
  local -a expr=()
  for ext in "$@"; do
    expr+=(-name "$ext" -o)
  done
  unset 'expr[${#expr[@]}-1]'
  find "$tree" \
    \( -path '*/bin/*' -o -path '*/obj/*' -o -path '*/node_modules/*' \
       -o -path '*/.venv/*' -o -path '*/dist/*' -o -path '*/.angular/*' \) -prune -o \
    -type f \( "${expr[@]}" \) -print 2>/dev/null
}

# Grep a pattern across a file list. Prints matches; returns 0 if any were found.
scan() {
  local pattern="$1"
  shift
  local files
  files="$(cat)"
  [ -n "$files" ] || return 1
  printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 grep -nIE "$pattern" 2>/dev/null
}

check() {
  local description="$1" pattern="$2" tree="$3"
  shift 3
  local hits
  hits="$(sources "$tree" "$@" | scan "$pattern")"
  if [ -n "$hits" ]; then
    printf '\n  \xe2\x9c\x97 %s\n' "$description"
    printf '%s\n' "$hits" | sed 's/^/      /'
    violations=$((violations + 1))
  fi
}

echo "Checking cross-deployable boundary (ADR-0001)..."

# ---------------------------------------------------------------- .NET -> RagCore
check ".NET build files reference RagCore" \
  'ragcore' dotnet '*.csproj' '*.sln' '*.props' '*.targets'

check ".NET source references RagCore" \
  'ragcore' dotnet '*.cs'

# ---------------------------------------------------------------- RagCore -> .NET
check "RagCore imports a Synthia (.NET) module" \
  '(^|[^A-Za-z_])(import|from)[[:space:]]+Synthia' ragcore '*.py'

check "RagCore names a .NET assembly" \
  'Synthia\.(Api|Modules|Contracts|Persistence|SharedKernel|Observability)' ragcore '*.py' '*.toml'

# --------------------------------------------- an HTTP client in either targeting the other
# Specification 13.4: there is no direct service-to-service path. A base address naming the other
# deployable is that path, however it is spelled.
check ".NET configures an HTTP client targeting RagCore" \
  '(BaseAddress|base_?[Uu]rl).{0,80}ragcore' dotnet '*.cs' '*.json'

check "RagCore configures an HTTP client targeting the monolith" \
  '(BaseAddress|base_?[Uu]rl).{0,80}(synthia-api|synthia\.api)' ragcore '*.py' '*.toml' '*.json'

# ------------------------------------------- the monolith owns no schema (ADR-0001, ADR-0003)
check ".NET calls a schema-owning EF API - Alembic owns every migration" \
  '(Database\.Migrate|EnsureCreated)[[:space:]]*\(' dotnet '*.cs'

migration_dirs="$(find dotnet -type d -name Migrations \
  \( -path '*/bin/*' -o -path '*/obj/*' \) -prune -o -type d -name Migrations -print 2>/dev/null)"
if [ -n "$migration_dirs" ]; then
  printf '\n  \xe2\x9c\x97 %s\n' ".NET contains an EF Migrations directory - the monolith owns no schema"
  printf '%s\n' "$migration_dirs" | sed 's/^/      /'
  violations=$((violations + 1))
fi

# ---------------------------------------------------------------- result
if [ "$violations" -gt 0 ]; then
  printf '\nBoundary check FAILED with %d violation(s).\n' "$violations"
  echo "The two deployables meet only at PostgreSQL (versioned views) and Service Bus (opaque"
  echo "triggers). If this dependency is genuinely needed it requires an ADR amending ADR-0001 -"
  echo "not a suppression here."
  exit 1
fi

printf '  \xe2\x9c\x93 No cross-deployable dependency found.\n'
printf '  \xe2\x9c\x93 The monolith owns no schema.\n'
exit 0
